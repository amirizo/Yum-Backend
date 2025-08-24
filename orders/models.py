from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
import uuid
from django.conf import settings
import math
User = get_user_model()
from authentication.models import Vendor, Driver  # import your profile models
import logging

logger = logging.getLogger(__name__)
class Category(models.Model):
    CATEGORY_TYPES = [
        ('food', 'Food'),
        ('grocery', 'Grocery'),
    ]
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='product_categories', null=True, blank=True)
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='food')
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ['vendor', 'name']  # Vendors can't have duplicate category names

    def __str__(self):
        if self.vendor:
            return f"{self.name} - {self.vendor.business_name}"
        return self.name


class Product(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('archived', 'Archived'),
    ]
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    image = models.ImageField(upload_to='products/', blank=True, null=True, 
                             help_text="Upload a high-quality image of your product")
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Available stock quantity")
    max_order_quantity = models.PositiveIntegerField(default=10, help_text="Maximum quantity a customer can order for this product")
    unit = models.CharField(max_length=20, default='piece', 
                           help_text="Unit of measurement (kg, piece, liter, etc.)")
    is_available = models.BooleanField(default=True)
    preparation_time = models.PositiveIntegerField(null=True, blank=True, 
                                                  help_text="Preparation time in minutes (for food items)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.name} - {self.vendor.business_name} {self.vendor.business_phone}"

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
            vendor_user = self.vendor.user
            context = {
                'vendor_name': f"{vendor_user.first_name} {vendor_user.last_name}",
                'product_name': self.name,
                'stock_quantity': self.stock_quantity,
                'unit': self.unit,
                'category_name': self.category.name if self.category else "N/A",
            }

            subject = f"Low Stock Alert - {self.name}"
            html_message = render_to_string('emails/ low_stock_alert.html', context)
            plain_message = render_to_string('emails/low_stock.txt', context)

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[vendor_user.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Low stock email sent to {vendor_user.email} for product {self.name}")

        except Exception as e:
            logger.error(f"Failed to send low stock email: {e}")

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
    
    country = models.CharField(max_length=100, default='Tanzania')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    place_id = models.CharField(max_length=255, blank=True)
    formatted_address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_default:
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
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='orders')
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_orders')
    
    # Order details
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Delivery information
    delivery_address = models.ForeignKey(DeliveryAddress, on_delete=models.CASCADE, null=True, blank=True)
    # Keep free-text address for guests or as fallback
    delivery_address_text = models.TextField(help_text="Delivery address as text for non-registered users", blank=True)

    # Explicit delivery address fields to capture full details at time of order
    delivery_street_number = models.CharField(max_length=50, blank=True)
    delivery_street_line2 = models.CharField(max_length=255, blank=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_state = models.CharField(max_length=100, blank=True)
    delivery_country = models.CharField(max_length=100, default='Tanzania', blank=True)
    delivery_place_id = models.CharField(max_length=255, blank=True)
    delivery_formatted_address = models.CharField(max_length=255, blank=True)
    delivery_phone = models.CharField(max_length=20, blank=True)

    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_instructions = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True, help_text="Customer's special instructions for the order")
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

    def set_delivery_from_address(self, delivery_address):
        """Populate order delivery fields from a DeliveryAddress instance.

        Call this before saving the Order to persist the address snapshot for the order.
        """
        try:
            if not delivery_address:
                return

            self.delivery_address = delivery_address
            # Fallbacks for various possible DeliveryAddress fields
            self.delivery_address_text = (delivery_address.formatted_address or delivery_address.street_address or '')
            # If DeliveryAddress has separate street number/line2 attributes, use them; otherwise leave blank
            self.delivery_street_number = getattr(delivery_address, 'street_number', '') or ''
            self.delivery_street_line2 = getattr(delivery_address, 'street_line2', '') or ''
            self.delivery_city = delivery_address.city or ''
            self.delivery_state = delivery_address.state or ''
            self.delivery_country = delivery_address.country or ''
            self.delivery_place_id = delivery_address.place_id or ''
            self.delivery_formatted_address = delivery_address.formatted_address or ''
            # Copy phone if available on delivery address
            self.delivery_phone = getattr(delivery_address, 'phone', '') or ''
            self.delivery_latitude = delivery_address.latitude
            self.delivery_longitude = delivery_address.longitude
        except Exception as e:
            logger.exception('Failed to populate delivery fields from DeliveryAddress: %s', e)

    def __str__(self):
        return f"Order {self.order_number} - {self.customer.first_name} {self.customer.last_name}"
        

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
        if not self.pk:  # Only on creation
            if self.product.stock_quantity >= self.quantity:
                self.product.stock_quantity -= self.quantity
                self.product.save()
            else:
                raise ValueError(f"Insufficient stock for {self.product.name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"


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
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='reviews')
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_reviews')
    
    # Ratings (1-5 stars)
    food_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    delivery_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    overall_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Comments
    comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.order.order_number} - {self.overall_rating} stars"




class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='carts', null=True, blank=True)
    session_key = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items.all())
    

    

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    special_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cart', 'product']

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    @property
    def total_price(self):
        return self.quantity * self.product.price

    def save(self, *args, **kwargs):
        # Ensure cart vendor matches product vendor
        if self.cart.vendor and self.cart.vendor != self.product.vendor:
            # Clear cart if switching vendors
            self.cart.items.all().delete()
            self.cart.vendor = self.product.vendor
            self.cart.save()
        elif not self.cart.vendor:
            self.cart.vendor = self.product.vendor
            self.cart.save()
        super().save(*args, **kwargs)




def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    if not all([lat1, lon1, lat2, lon2]):
        return 0
    
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of Earth in kilometers
    r = 6371
    return c * r


def calculate_delivery_fee(customer_lat, customer_lon, vendor_lat, vendor_lon):
    """Calculate delivery fee based on distance
    
    Logic:
    - Distance ≤ 3km: 2000 TSH per km
    - Distance ≥ 4km: 700 TSH per km
    
    Examples:
    - 2.5km: 2.5 × 2000 = 5000 TSH
    - 5km: 5 × 700 = 3500 TSH
    """
    distance = calculate_distance(customer_lat, customer_lon, vendor_lat, vendor_lon)
    
    if distance <= 3:
        # For distances ≤ 3km: charge 2000 TSH per km
        return distance * 2000
    else:
        # For distances ≥ 4km: charge 700 TSH per km for total distance
        return distance * 700