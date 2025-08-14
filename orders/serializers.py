from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Avg
from .models import (
    Category, Product, ProductImage, ProductVariant, ProductReview,
    DeliveryAddress, Order, OrderItem, OrderStatusHistory, Review
)
from authentication.serializers import UserSerializer

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'parent', 'is_active', 
                 'sort_order', 'subcategories', 'product_count', 'full_path', 'created_at']
        read_only_fields = ['created_at']

    def get_subcategories(self, obj):
        if obj.subcategories.exists():
            return CategorySerializer(obj.subcategories.filter(is_active=True), many=True).data
        return []

    def get_product_count(self, obj):
        return obj.products.filter(status='active').count()

    def get_full_path(self, obj):
        return obj.get_full_path()

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'sort_order', 'created_at']
        read_only_fields = ['created_at']

class ProductVariantSerializer(serializers.ModelSerializer):
    final_price = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ['id', 'name', 'value', 'price_adjustment', 'sku', 
                 'inventory_quantity', 'is_active', 'final_price', 'created_at']
        read_only_fields = ['created_at']

    def get_final_price(self, obj):
        return float(obj.get_final_price())

class ProductReviewSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = ['id', 'customer', 'customer_name', 'rating', 'title', 'comment', 
                 'is_verified_purchase', 'is_approved', 'created_at']
        read_only_fields = ['customer', 'is_verified_purchase', 'created_at']

    def get_customer_name(self, obj):
        return f"{obj.customer.first_name} {obj.customer.last_name}".strip() or obj.customer.username

class ProductSerializer(serializers.ModelSerializer):
    vendor = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    
    # Calculated fields
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'vendor', 'category', 'category_id', 'name', 'description', 
            'short_description', 'sku', 'barcode', 'price', 'compare_price', 
            'cost_price', 'track_inventory', 'inventory_quantity', 'low_stock_threshold',
            'allow_backorder', 'weight', 'unit', 'unit_size', 'featured_image',
            'status', 'is_available', 'is_featured', 'preparation_time',
            'is_vegetarian', 'is_vegan', 'is_gluten_free', 'spice_level',
            'meta_title', 'meta_description', 'tags', 'images', 'variants',
            'reviews', 'average_rating', 'review_count', 'discount_percentage',
            'is_in_stock', 'is_low_stock', 'created_at', 'updated_at'
        ]
        read_only_fields = ['vendor', 'created_at', 'updated_at']

    def get_average_rating(self, obj):
        avg = obj.product_reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg']
        return round(avg, 2) if avg else 0

    def get_review_count(self, obj):
        return obj.product_reviews.filter(is_approved=True).count()

    def get_discount_percentage(self, obj):
        return obj.get_discount_percentage()

    def get_is_in_stock(self, obj):
        return obj.is_in_stock()

    def get_is_low_stock(self, obj):
        return obj.is_low_stock()

    def create(self, validated_data):
        validated_data['vendor'] = self.context['request'].user
        return super().create(validated_data)


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, required=False)
    variants = ProductVariantSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            'category', 'name', 'description', 'short_description', 'sku', 'barcode',
            'price', 'compare_price', 'cost_price', 'track_inventory', 'inventory_quantity',
            'low_stock_threshold', 'allow_backorder', 'weight', 'unit', 'unit_size',
            'featured_image', 'status', 'is_available', 'is_featured', 'preparation_time',
            'is_vegetarian', 'is_vegan', 'is_gluten_free', 'spice_level',
            'meta_title', 'meta_description', 'tags', 'images', 'variants'
        ]

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        variants_data = validated_data.pop('variants', [])
        
        validated_data['vendor'] = self.context['request'].user
        product = Product.objects.create(**validated_data)
        
        # Create images
        for image_data in images_data:
            ProductImage.objects.create(product=product, **image_data)
        
        # Create variants
        for variant_data in variants_data:
            ProductVariant.objects.create(product=product, **variant_data)
        
        return product

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', [])
        variants_data = validated_data.pop('variants', [])
        
        # Update product
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update images if provided
        if images_data:
            instance.images.all().delete()
            for image_data in images_data:
                ProductImage.objects.create(product=instance, **image_data)
        
        # Update variants if provided
        if variants_data:
            instance.variants.all().delete()
            for variant_data in variants_data:
                ProductVariant.objects.create(product=instance, **variant_data)
        
        return instance

class VendorProductListSerializer(serializers.ModelSerializer):
    """Simplified serializer for vendor product listings"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_in_stock = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    variant_count = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category_name', 'price', 'inventory_quantity',
            'status', 'is_available', 'is_featured', 'is_in_stock', 'is_low_stock',
            'variant_count', 'image_count', 'created_at', 'updated_at'
        ]

    def get_is_in_stock(self, obj):
        return obj.is_in_stock()

    def get_is_low_stock(self, obj):
        return obj.is_low_stock()

    def get_variant_count(self, obj):
        return obj.variants.filter(is_active=True).count()

    def get_image_count(self, obj):
        return obj.images.count()

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
    variant = ProductVariantSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    variant_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = OrderItem
        fields = '__all__'
        read_only_fields = ['order', 'unit_price', 'total_price']

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value, status='active', is_available=True)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or not available")

    def validate_variant_id(self, value):
        if value:
            try:
                variant = ProductVariant.objects.get(id=value, is_active=True)
                return value
            except ProductVariant.DoesNotExist:
                raise serializers.ValidationError("Product variant not found or not available")
        return value

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
            variant = None
            if item_data.get('variant_id'):
                variant = ProductVariant.objects.get(id=item_data['variant_id'])
            
            if vendor is None:
                vendor = product.vendor
            elif vendor != product.vendor:
                raise serializers.ValidationError("All items must be from the same vendor")
            
            # Calculate price (with variant adjustment if applicable)
            unit_price = variant.get_final_price() if variant else product.price
            item_total = unit_price * item_data['quantity']
            subtotal += item_total

        # Get vendor profile for delivery fee
        try:
            vendor_profile = vendor.vendor_profile
            delivery_fee = vendor_profile.delivery_fee
        except:
            delivery_fee = 5.00  # Default delivery fee

        # Calculate taxes
        tax_rate = 0.18  # 18% VAT for Tanzania
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

        # Create order items
        for item_data in items_data:
            product = Product.objects.get(id=item_data['product_id'])
            variant = None
            if item_data.get('variant_id'):
                variant = ProductVariant.objects.get(id=item_data['variant_id'])
            
            unit_price = variant.get_final_price() if variant else product.price
            
            OrderItem.objects.create(
                order=order,
                product=product,
                variant=variant,
                quantity=item_data['quantity'],
                unit_price=unit_price,
                special_instructions=item_data.get('special_instructions', '')
            )
            
            # Update inventory if tracking is enabled
            if product.track_inventory:
                product.inventory_quantity -= item_data['quantity']
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
