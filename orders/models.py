from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.mail import send_mail
from django.utils import timezone
import uuid
from django.conf import settings

User = get_user_model()


class Category(models.Model):
    CATEGORY_TYPES = [
        ('food', 'Food'),
        ('grocery', 'Grocery'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='food')
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('archived', 'Archived'),
    ]
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    image = models.ImageField(upload_to='products/', blank=True, null=True, 
                             help_text="Upload a high-quality image of your product")
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Available stock quantity")
    unit = models.CharField(max_length=20, default='piece', 
                           help_text="Unit of measurement (kg, piece, liter, etc.)")
    is_available = models.BooleanField(default=True)
    preparation_time = models.PositiveIntegerField(null=True, blank=True, 
                                                  help_text="Preparation time in minutes (for food items)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.name} - {self.vendor.first_name} {self.vendor.last_name}"

    @property
    def is_low_stock(self):
        return self.stock_quantity < 5

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_stock = 0
        
        if not is_new:
            old_product = Product.objects.get(pk=self.pk)
            old_stock = old_product.stock_quantity
        
        super().save(*args, **kwargs)
        
        if not is_new and old_stock >= 5 and self.stock_quantity < 5:
            self.send_low_stock_email()

    def send_low_stock_email(self):
        """Send low stock alert email to vendor"""
        try:
            subject = f'Low Stock Alert - {self.name}'
            message = f"""
            Dear {self.vendor.first_name} {self.vendor.last_name},

            Your product "{self.name}" is running low on stock.

            Current Stock: {self.stock_quantity} {self.unit}
            Product Category: {self.category.name}

            Please restock this item to avoid running out of inventory.

            Best regards,
            YumExpress Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.vendor.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Failed to send low stock email: {e}")

    class Meta:
        ordering = ['-created_at']


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
