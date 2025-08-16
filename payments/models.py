from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
import uuid
import secrets
import string
from authentication.models import Vendor
User = get_user_model()

class PaymentMethod(models.Model):
    PAYMENT_TYPES = [
        ('card', 'Credit/Debit Card'),
        ('mobile_money', 'Mobile Money'),
        ('cash', 'Cash on Delivery'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    
    # Card details (for display purposes only)
    card_brand = models.CharField(max_length=20, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)
    
    # Mobile money details
    mobile_provider = models.CharField(max_length=50, blank=True)  # TIGO-PESA, M-PESA, AIRTEL-MONEY
    phone_number = models.CharField(max_length=15, blank=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other payment methods for this user to not default
            PaymentMethod.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.payment_type == 'card':
            return f"{self.card_brand} ending in {self.card_last4}"
        elif self.payment_type == 'mobile_money':
            return f"{self.mobile_provider} - {self.phone_number}"
        return f"{self.payment_type}"

    class Meta:
        ordering = ['-is_default', '-created_at']

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
        ('pending_admin_approval', 'Pending Admin Approval'),
    ]

    PAYMENT_TYPES = [
        ('card', 'Credit/Debit Card'),
        ('mobile_money', 'Mobile Money'),
        ('cash', 'Cash on Delivery'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='payment')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    
    # ClickPesa integration
    clickpesa_order_reference = models.CharField(max_length=100, unique=True, blank=True)
    clickpesa_payment_reference = models.CharField(max_length=100, blank=True, null=True)
    clickpesa_payment_link = models.URLField(blank=True)
    
    # Payment details
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='card')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='TZS')
    status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Mobile Money specific fields
    mobile_number = models.CharField(max_length=15, blank=True)
    mobile_provider = models.CharField(max_length=20, blank=True)
    
    # Transaction details
    transaction_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Metadata
    failure_reason = models.TextField(blank=True)
    receipt_url = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def generate_unique_order_reference(self):
        """Generate a unique order reference for ClickPesa"""
        while True:
            # Generate a random string with timestamp
            timestamp = str(int(self.created_at.timestamp())) if self.created_at else str(int(uuid.uuid4().time))
            random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            reference = f"YUM{timestamp[-6:]}{random_part}"
            
            # Check if this reference already exists
            if not Payment.objects.filter(clickpesa_order_reference=reference).exists():
                return reference

    def save(self, *args, **kwargs):
        if not self.clickpesa_order_reference:
            # Set created_at if not set (for new objects)
            if not self.created_at:
                from django.utils import timezone
                self.created_at = timezone.now()
            self.clickpesa_order_reference = self.generate_unique_order_reference()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment {self.id} - {self.order.order_number} - {self.amount} {self.currency}"

    class Meta:
        ordering = ['-created_at']

class Refund(models.Model):
    REFUND_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]

    REFUND_REASON_CHOICES = [
        ('duplicate', 'Duplicate'),
        ('fraudulent', 'Fraudulent'),
        ('requested_by_customer', 'Requested by Customer'),
        ('order_canceled', 'Order Canceled'),
        ('vendor_rejected', 'Vendor Rejected Order'),  # Added for vendor rejection
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    clickpesa_refund_id = models.CharField(max_length=200, blank=True)  # Changed from stripe to clickpesa
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='TZS')  # Changed default to TZS
    status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='pending')
    reason = models.CharField(max_length=30, choices=REFUND_REASON_CHOICES)
    
    # Metadata
    description = models.TextField(blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Refund {self.id} - {self.amount} {self.currency}"

    class Meta:
        ordering = ['-created_at']

class PaymentWebhookEvent(models.Model):
    clickpesa_event_id = models.CharField(max_length=200, unique=True)  # Changed from stripe to clickpesa
    event_type = models.CharField(max_length=100)
    processed = models.BooleanField(default=False)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} - {self.clickpesa_event_id}"

    class Meta:
        ordering = ['-created_at']

class PayoutRequest(models.Model):
    PAYOUT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='payout_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='TZS')  # Changed default to TZS
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='pending')
    
    # Mobile money payout details
    phone_number = models.CharField(max_length=15, blank=True)  # Added for mobile money payouts
    mobile_provider = models.CharField(max_length=50, blank=True)
    
    # Bank account details (for future use)
    bank_account_last4 = models.CharField(max_length=4, blank=True)
    
    # Metadata
    description = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout {self.vendor.first_name} {self.vendor.last_name} - {self.amount} {self.currency}"

    class Meta:
        ordering = ['-created_at']
