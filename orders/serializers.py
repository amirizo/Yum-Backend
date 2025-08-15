from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Category, Product, DeliveryAddress, Order, OrderItem, OrderStatusHistory
from authentication.serializers import UserSerializer
from decimal import Decimal
User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'category_type', 'is_active', 'product_count', 'created_at']
        read_only_fields = ['created_at', 'product_count']

    def get_product_count(self, obj):
        return obj.products.filter(is_available=True).count()

class ProductSerializer(serializers.ModelSerializer):
    vendor = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    image = serializers.ImageField(required=True)  # ✅ Image required
    stock_quantity = serializers.IntegerField(required=True, min_value=0)  # ✅ Stock required
    is_in_stock = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'vendor', 'category', 'category_id', 'name', 'description', 
            'price', 'stock_quantity', 'unit', 'image', 'is_available', 
            'preparation_time', 'is_in_stock', 'is_low_stock',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['vendor', 'created_at', 'updated_at']

    def get_is_in_stock(self, obj):
        return obj.stock_quantity > 0

    def get_is_low_stock(self, obj):
        return obj.stock_quantity <= 10  # Low stock threshold

    def create(self, validated_data):
        validated_data['vendor'] = self.context['request'].user
        return super().create(validated_data)

class DeliveryAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAddress
        fields = '__all__'
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = OrderItem
        fields = '__all__'
        read_only_fields = ['order', 'unit_price', 'total_price']

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value, is_available=True)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or not available")

class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    delivery_address_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Order
        fields = ['items', 'delivery_address_id', 'delivery_instructions']

    def validate_delivery_address_id(self, value):
        user = self.context['request'].user
        try:
            address = DeliveryAddress.objects.get(id=value, user=user)
            return value
        except DeliveryAddress.DoesNotExist:
            raise serializers.ValidationError("Delivery address not found")

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Order must contain at least one item")
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        delivery_address_id = validated_data.pop('delivery_address_id')
        
        # Get delivery address
        delivery_address = DeliveryAddress.objects.get(id=delivery_address_id)
        
        # Calculate totals
        subtotal = 0
        vendor = None
        
        for item_data in items_data:
            product = Product.objects.get(id=item_data['product_id'])
            if vendor is None:
                vendor = product.vendor
            elif vendor != product.vendor:
                raise serializers.ValidationError("All items must be from the same vendor")
            
            item_total = product.price * item_data['quantity']
            subtotal += item_total

        # Calculate fees and taxes
        delivery_fee = Decimal('5.00')
        tax_rate = Decimal('0.08')
        tax_amount = subtotal * tax_rate
        total_amount = subtotal + delivery_fee + tax_amount

        # Create order
        order = Order.objects.create(
            customer=self.context['request'].user,
            vendor=vendor,
            delivery_address=delivery_address,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            tax_amount=tax_amount,
            total_amount=total_amount,
            **validated_data
        )

        # Create order items and update stock
        for item_data in items_data:
            product = Product.objects.get(id=item_data['product_id'])
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item_data['quantity'],
                unit_price=product.price,
                special_instructions=item_data.get('special_instructions', '')
            )
            
            if product.stock_quantity >= item_data['quantity']:
                product.stock_quantity -= item_data['quantity']
                product.save()

        # Create initial status history
        OrderStatusHistory.objects.create(
            order=order,
            status='pending',
            changed_by=self.context['request'].user,
            notes='Order created'
        )

        return order

class OrderSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    vendor = UserSerializer(read_only=True)
    driver = UserSerializer(read_only=True)
    delivery_address = DeliveryAddressSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = '__all__'

class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by = UserSerializer(read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = '__all__'

class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    notes = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = ['status', 'notes']

    def update(self, instance, validated_data):
        notes = validated_data.pop('notes', '')
        old_status = instance.status
        new_status = validated_data.get('status', old_status)
        
        # Update order
        instance = super().update(instance, validated_data)
        
        # Create status history if status changed
        if old_status != new_status:
            OrderStatusHistory.objects.create(
                order=instance,
                status=new_status,
                changed_by=self.context['request'].user,
                notes=notes
            )
        
        return instance
