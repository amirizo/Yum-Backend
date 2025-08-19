from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Category, Product,ProductVariant, DeliveryAddress, Order, OrderItem, OrderItem, OrderStatusHistory, Review, CartItem, Cart
from authentication.serializers import UserSerializer, VendorProfileSerializer, VendorLocationSerializer
from decimal import Decimal, ROUND_HALF_UP
from authentication.models import Vendor, Driver
from rest_framework.exceptions import PermissionDenied
User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'category_type', 'is_active', 'product_count', 'vendor_name', 'created_at']
        read_only_fields = ['created_at', 'product_count', 'vendor_name']

    def get_product_count(self, obj):
        return obj.products.filter(is_available=True).count()
    
    def get_vendor_name(self, obj):
        return obj.vendor.business_name if obj.vendor else "Global"


class VendorCategorySerializer(serializers.ModelSerializer):
    """Serializer for vendor category management"""
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'category_type', 'is_active', 'product_count', 'created_at']
        read_only_fields = ['created_at', 'product_count']

    def get_product_count(self, obj):
        return obj.products.filter(is_available=True).count()
    
    def validate_name(self, value):
        """Ensure category name is unique for this vendor"""
        vendor = self.context['request'].user.vendor_profile
        
        # For updates, exclude current instance
        if self.instance:
            existing = Category.objects.filter(vendor=vendor, name=value).exclude(id=self.instance.id)
        else:
            existing = Category.objects.filter(vendor=vendor, name=value)
        
        if existing.exists():
            raise serializers.ValidationError("You already have a category with this name.")
        
        return value

    def create(self, validated_data):
        """Automatically set vendor when creating category"""
        vendor = self.context['request'].user.vendor_profile
        validated_data['vendor'] = vendor
        return super().create(validated_data)
    




class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['id', 'name', 'value', 'price_adjustment', 'sku', 'inventory_quantity', 'is_active']

class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, required=False)
    vendor = VendorProfileSerializer
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
            'created_at', 'updated_at', 'variants'
        ]
        read_only_fields = ['vendor', 'created_at', 'updated_at']

    def get_is_in_stock(self, obj):
        return obj.stock_quantity > 0

    def get_is_low_stock(self, obj):
        return obj.stock_quantity <= 10  # Low stock threshold

    # def create(self, validated_data):
    #     validated_data['vendor'] = self.context['request'].user.vendor_profile
    #     return super().create(validated_data)

    def create(self, validated_data):
        # Extract variants if provided
        variants_data = validated_data.pop('variants', [])
        validated_data['vendor'] = self.context['request'].user.vendor_profile
        product = Product.objects.create(**validated_data)

        # Create variants
        for variant in variants_data:
            ProductVariant.objects.create(product=product, **variant)
        return product

    def update(self, instance, validated_data):
        # Handle variants on update
        variants_data = validated_data.pop('variants', [])
        instance = super().update(instance, validated_data)

        if variants_data:
            instance.variants.all().delete()  # Replace all
            for variant in variants_data:
                ProductVariant.objects.create(product=instance, **variant)
        return instance

class DeliveryAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAddress
        fields = '__all__'
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        if 'user' not in validated_data and self.context.get('request'):
            validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        # Ensure coordinates or street_address is present
        if not data.get('latitude') or not data.get('longitude'):
            if not data.get('street_address'):
                raise serializers.ValidationError("Either coordinates or street address is required")
        return data
    

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
        
    
    def validate_quantity(self, value):
        product = self.instance.product if self.instance else self.initial_data.get('product')
        if isinstance(product, int):  # if product is passed as ID
            from .models import Product
            product = Product.objects.get(id=product, is_available=True)
        if value > product.max_order_quantity:
            raise serializers.ValidationError(f"Cannot order more than {product.max_order_quantity} units of {product.name}.")
        return value


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    delivery_address_id = serializers.IntegerField(write_only=True, required=False)
    delivery_address = DeliveryAddressSerializer(write_only=True, required=False)

    class Meta:
        model = Order
        fields = ['items', 'delivery_address_id', 'delivery_address', 'delivery_instructions']

    def validate(self, data):
        user = self.context['request'].user
        if user.user_type != 'customer':
            raise PermissionDenied("Only customers can create orders.")

        # Either delivery_address_id or delivery_address required
        if not data.get('delivery_address_id') and not data.get('delivery_address'):
            raise serializers.ValidationError("Either delivery_address_id or delivery_address is required")
        if data.get('delivery_address_id') and data.get('delivery_address'):
            raise serializers.ValidationError("Provide either delivery_address_id or delivery_address, not both")
        return data

    
   

    def validate_delivery_address_id(self, value):
        user = self.context['request'].user
        try:
            address = DeliveryAddress.objects.get(id=value, user=user)
            return value
        except DeliveryAddress.DoesNotExist:
            raise serializers.ValidationError("Delivery address not found")

    def validate_items(self, value):
        for item in value:
            product = item['product']
            if item['quantity'] > product.max_order_quantity:
                raise serializers.ValidationError(
                    f"Quantity for {product.name} exceeds maximum allowed ({product.max_order_quantity})."
                )

        if not value:
            raise serializers.ValidationError("Order must contain at least one item")

        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        delivery_address_id = validated_data.pop('delivery_address_id', None)
        delivery_address_data = validated_data.pop('delivery_address', None)

        # Get or create delivery address
        if delivery_address_id:
            delivery_address = DeliveryAddress.objects.get(id=delivery_address_id)
        else:
            serializer = DeliveryAddressSerializer(data=delivery_address_data, context=self.context)
            serializer.is_valid(raise_exception=True)
            delivery_address = serializer.save(user=self.context['request'].user)

        # Calculate subtotal
        subtotal = Decimal('0.00')
        vendor = None

        for item_data in items_data:
            product = Product.objects.get(id=item_data['product_id'])
            if vendor is None:
                vendor = product.vendor
            elif vendor != product.vendor:
                raise serializers.ValidationError("All items must be from the same vendor")

            item_total = product.price * Decimal(item_data['quantity'])
            subtotal += item_total

        # Calculate delivery fee (use distance-based function if available)
        delivery_fee = Decimal('2000.00')
        vendor_profile = getattr(vendor, 'vendor_profile', None)
        if (vendor_profile and delivery_address.latitude and delivery_address.longitude and
            vendor_profile.business_latitude and vendor_profile.business_longitude):
            from .models import calculate_delivery_fee
            delivery_fee = Decimal(calculate_delivery_fee(
                delivery_address.latitude,
                delivery_address.longitude,
                vendor_profile.business_latitude,
                vendor_profile.business_longitude
            )).quantize(Decimal("0.00"))

        # Taxes
        tax_rate = Decimal('0.00')  # Replace with TZS tax rate if any
        tax_amount = (subtotal * tax_rate).quantize(Decimal("0.00"))
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

    



class VendorSerializer(serializers.ModelSerializer):
    location = VendorLocationSerializer(source='primary_location', read_only=True)
    class Meta:
        model = Vendor
        fields = ['id', 'business_name', 'business_phone', 'business_email', 'location']  # add fields you need

class DriverSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    phone = serializers.CharField(source='user.phone_number', read_only=True)  # or `user.phone` if you extended User model
    class Meta:
        model = Driver
        fields = ['id', 'first_name', 'last_name', 'phone']


class OrderSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    vendor = VendorSerializer(read_only=True)
    driver = DriverSerializer(read_only=True)
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







class ReviewSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    order = OrderSerializer(read_only=True)

    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['customer', 'order', 'vendor', 'driver', 'created_at']

    def create(self, validated_data):
        order_id = self.context['order_id']
        order = Order.objects.get(id=order_id)
        
        validated_data['customer'] = self.context['request'].user
        validated_data['order'] = order
        validated_data['vendor'] = order.vendor
        validated_data['driver'] = order.driver
        
        return super().create(validated_data)

class VendorRestaurantSerializer(serializers.ModelSerializer):
    """Serializer for displaying vendor restaurant page with business info and products"""
    vendor_profile = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    total_products = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'vendor_profile', 'products', 'total_products', 'is_open']
    
    def get_vendor_profile(self, obj):
        """Get vendor business profile information"""
        try:
            from authentication.serializers import VendorProfileSerializer
            return VendorProfileSerializer(obj.vendor_profile).data
        except:
            return None
    
    def get_products(self, obj):
        """Get vendor's available products"""
        products = Product.objects.filter(vendor=obj, is_available=True).order_by('-created_at')
        return ProductSerializer(products, many=True).data
    
    def get_total_products(self, obj):
        """Get total count of vendor's available products"""
        return Product.objects.filter(vendor=obj, is_available=True).count()
    
    def get_is_open(self, obj):
        """Check if vendor is currently open based on business hours"""
        try:
            return obj.vendor_profile.is_open_now()
        except:
            return True

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'special_instructions', 'total_price', 'created_at']
        read_only_fields = ['id', 'total_price', 'created_at']

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value, is_available=True)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or not available")

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    vendor = UserSerializer(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'vendor', 'items', 'total_amount', 'total_items', 'created_at', 'updated_at']
        read_only_fields = ['id', 'vendor', 'total_amount', 'total_items', 'created_at', 'updated_at']

class VendorWithProductsSerializer(serializers.ModelSerializer):
    vendor_profile = serializers.SerializerMethodField()
    products = ProductSerializer(many=True, read_only=True)
    total_products = serializers.IntegerField(read_only=True)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)
    business_name = serializers.SerializerMethodField()
    business_type = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'business_name', 'business_type', 'vendor_profile', 'products', 'total_products', 'average_rating', 'is_open']

    def get_vendor_profile(self, obj):
        if hasattr(obj, 'vendor_profile'):
            return VendorProfileSerializer(obj.vendor_profile).data
        return None
    
    def get_business_name(self, obj):
        if hasattr(obj, 'vendor_profile'):
            return obj.vendor_profile.business_name
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def get_business_type(self, obj):
        if hasattr(obj, 'vendor_profile'):
            return obj.vendor_profile.get_business_type_display()
        return None
    
    def get_is_open(self, obj):
        if hasattr(obj, 'vendor_profile'):
            return obj.vendor_profile.is_open_now()
        return True



class CheckoutSerializer(serializers.Serializer):
    vendor_id = serializers.IntegerField()
    cart_id = serializers.UUIDField(required=False)  # For anonymous users
    delivery_address = DeliveryAddressSerializer()