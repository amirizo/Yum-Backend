from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

User = get_user_model()


class Category(models.Model):
    CATEGORY_TYPES = [
        ('groceries', 'Groceries'),
        ('foods', 'Foods'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True, help_text="High-quality category image")
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='foods')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_category_type_display()})"

    def get_full_path(self):
        """Get full category path for nested categories"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name


class Product(models.Model):
    PRODUCT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('out_of_stock', 'Out of Stock'),
        ('discontinued', 'Discontinued'),
    ]
    
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('kg', 'Kilogram'),
        ('gram', 'Gram'),
        ('liter', 'Liter'),
        ('ml', 'Milliliter'),
        ('pack', 'Pack'),
        ('box', 'Box'),
        ('bottle', 'Bottle'),
        ('can', 'Can'),
    ]

    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    
    # Basic product information
    name = models.CharField(max_length=200)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    sku = models.CharField(max_length=100, blank=True, help_text="Stock Keeping Unit")
    barcode = models.CharField(max_length=100, blank=True)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Original price for discount display")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Cost price for profit calculation")
    
    # Inventory management
    track_inventory = models.BooleanField(default=True)
    inventory_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    allow_backorder = models.BooleanField(default=False)
    
    # Product specifications
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Weight in grams")
    unit = models.CharField(max_length=50, blank=True, help_text="Unit of measurement (e.g., kg, pieces, liters)")
    unit_size = models.CharField(max_length=50, blank=True, help_text="e.g., 500ml, 1kg, Large")
    
    # Images
    image = models.ImageField(
        upload_to='products/', 
        blank=True, 
        null=True, 
        help_text="High-quality product image (recommended: 800x800px or higher)"
    )
    
    # Status and availability
    status = models.CharField(max_length=20, choices=PRODUCT_STATUS_CHOICES, default='active')
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Restaurant specific fields
    preparation_time = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Preparation time in minutes (for food items)"
    )
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_gluten_free = models.BooleanField(default=False)
    spice_level = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)], help_text="Spice level 0-5")
    
    # Grocery specific fields
    stock_quantity = models.PositiveIntegerField(
        default=0, 
        help_text="Available stock quantity (for grocery items)"
    )
    
    # SEO and metadata
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.vendor.first_name} {self.vendor.last_name}"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['vendor', 'sku']
    
    def is_in_stock(self):
        """Check if product is in stock"""
        if not self.track_inventory:
            return self.is_available
        return self.inventory_quantity > 0 or self.allow_backorder
    
    def is_low_stock(self):
        """Check if product is low in stock"""
        if not self.track_inventory:
            return False
        return self.inventory_quantity <= self.low_stock_threshold
    
    def get_discount_percentage(self):
        """Calculate discount percentage if compare_price is set"""
        if self.compare_price and self.compare_price > self.price:
            return round(((self.compare_price - self.price) / self.compare_price) * 100, 2)
        return 0
    
    @property
    def is_food_item(self):
        return self.category.category_type == 'foods'
    
    @property
    def is_grocery_item(self):
        return self.category.category_type == 'groceries'


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sort_order', 'created_at']
    
    def __str__(self):
        return f"Image for {self.product.name}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=100, help_text="e.g., Size, Color, Flavor")
    value = models.CharField(max_length=100, help_text="e.g., Large, Red, Chocolate")
    
    # Pricing override
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Price difference from base product")
    
    # Inventory override
    sku = models.CharField(max_length=100, blank=True)
    inventory_quantity = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['product', 'name', 'value']
    
    def __str__(self):
        return f"{self.product.name} - {self.name}: {self.value}"
    
    def get_final_price(self):
        """Get final price including adjustment"""
        return self.product.price + self.price_adjustment


class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_reviews')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews')
    order_item = models.ForeignKey('OrderItem', on_delete=models.CASCADE, null=True, blank=True)
    
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)
    
    # Review status
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['product', 'customer', 'order_item']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review for {self.product.name} by {self.customer.username}"


class DeliveryAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50, help_text="e.g., Home, Office")
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='Tanzania')  # Updated default country
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other addresses for this user to not default
            DeliveryAddress.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label} - {self.street_address}"

    class Meta:
        verbose_name_plural = "Delivery Addresses"


class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendor_orders')
    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_orders')
    
    # Order details
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Delivery information
    delivery_address = models.ForeignKey(DeliveryAddress, on_delete=models.CASCADE)
    delivery_instructions = models.TextField(blank=True)
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    actual_delivery_time = models.DateTimeField(null=True, blank=True)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number
            import random
            import string
            self.order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_number} - {self.customer.username}"

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)  # Added variant support
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    special_instructions = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        variant_info = f" ({self.variant.name}: {self.variant.value})" if self.variant else ""
        return f"{self.quantity}x {self.product.name}{variant_info}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Order.ORDER_STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.status} at {self.timestamp}"

    class Meta:
        verbose_name_plural = "Order Status Histories"
        ordering = ['-timestamp']


class Review(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vendor_reviews')
    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_reviews')
    
    # Ratings (1-5 stars)
    food_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    delivery_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    overall_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Comments
    comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.order.order_number} - {self.overall_rating} stars"
