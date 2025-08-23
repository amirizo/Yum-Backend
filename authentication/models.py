from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.html import format_html
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid
import random




class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)
    
class User(AbstractUser):
    USER_TYPES = (
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('driver', 'Driver'),
        ('admin', 'Admin'),
    )
    
    username = None
    email = models.EmailField(unique=True)
    
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='customer')
    phone_number = models.CharField(max_length=15, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    
    # Account status fields
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()  # <--- use custom manager

    def __str__(self):
        return f"{self.email} ({self.user_type})"
    
    def soft_delete(self, reason=""):
        """Soft delete user account"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deletion_reason = reason
        self.is_active = False  # Disable account
        self.save()
    
    def restore_account(self):
        """Restore soft deleted account"""
        self.is_deleted = False
        self.deleted_at = None
        self.deletion_reason = ""
        self.is_active = True
        self.save()
    


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Verification token for {self.user.email}"

    


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Password reset for {self.user.email}"

class LoginAttempt(models.Model):
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    success = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True)

    def __str__(self):
        return f"Login attempt for {self.email} at {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']

class TemporaryPassword(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    temp_password = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Temporary password for {self.user.email}"



class OTPVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField(null=True, blank=True)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)

    def save(self, *args, **kwargs):
        if not self.otp_code:
            self.otp_code = str(random.randint(100000, 999999))
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def can_attempt(self):
        return self.attempts < self.max_attempts

    def __str__(self):
        return f"OTP for {self.email} - {self.otp_code}"

    class Meta:
        ordering = ['-created_at']


class Vendor(models.Model):
    VENDOR_TYPES = (
        ('restaurant', 'Restaurant'),
        ('grocery', 'Grocery Store'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('inactive', 'Inactive'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    
    business_name = models.CharField(max_length=200)
    business_type = models.CharField(max_length=20, choices=VENDOR_TYPES, default='restaurant')
    business_description = models.TextField(blank=True)
    business_address = models.TextField()
    business_phone = models.CharField(max_length=15)
    business_email = models.EmailField(blank=True)
    business_license = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    
    logo = models.ImageField(upload_to='vendor_logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='vendor_covers/', blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_verified = models.BooleanField(default=False)
    verification_documents = models.JSONField(default=dict, blank=True)
    
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_orders = models.PositiveIntegerField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)
    
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    minimum_order_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    delivery_radius = models.PositiveIntegerField(default=5, help_text="Delivery radius in kilometers")
    average_preparation_time = models.PositiveIntegerField(default=30, help_text="Average preparation time in minutes")


    accepts_cash = models.BooleanField(default=True)
    accepts_card = models.BooleanField(default=True)
    accepts_mobile_money = models.BooleanField(default=True)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_vendors')

    def __str__(self):
        return self.business_name
    
    def approve(self, approved_by_user):
        """Approve vendor profile"""
        self.status = 'active'
        self.is_verified = True
        self.approved_at = timezone.now()
        self.approved_by = approved_by_user
        self.save()
    
    def is_open_now(self):
        """Check if vendor is currently open"""
        now = timezone.now()
        current_day = now.strftime('%A').lower()
        current_time = now.time()
        
        try:
            opening_hours = self.opening_hours.get(day_of_week=current_day)
            if opening_hours.is_closed:
                return False
            return opening_hours.opening_time <= current_time <= opening_hours.closing_time
        except BusinessHours.DoesNotExist:
            return False

    @property
    def primary_location(self):
        """Return the primary vendor location, or None if not set"""
        return self.locations.filter(is_primary=True).first()




class BusinessHours(models.Model):
    DAYS_OF_WEEK = (
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    )
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='opening_hours')
    day_of_week = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    is_closed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['vendor', 'day_of_week']
        verbose_name_plural = "Business Hours"
    
    def __str__(self):
        if self.is_closed:
            return f"{self.vendor.business_name} - {self.day_of_week}: Closed"
        return f"{self.vendor.business_name} - {self.day_of_week}: {self.opening_time} - {self.closing_time}"

class VendorLocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='locations')
    
    # Location details
    name = models.CharField(max_length=200, help_text="Branch name or identifier")
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
   
    country = models.CharField(max_length=100, default='Tanzania')
    
    # Coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    
    # Location settings
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    
    # Delivery settings for this location
    delivery_radius = models.PositiveIntegerField(default=5, help_text="Delivery radius in kilometers")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            # Set all other locations for this vendor to not primary
            VendorLocation.objects.filter(vendor=self.vendor, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.vendor.business_name} - {self.name}"
    
    class Meta:
        ordering = ['-is_primary', 'name']
   

class VendorCategory(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['vendor', 'name']
        verbose_name_plural = "Vendor Categories"
    
    def __str__(self):
        return f"{self.vendor.business_name} - {self.name}"











class Driver(models.Model):
    VEHICLE_TYPES = (
        ('bike', 'Motorcycle/Bike'),

    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    license_number = models.CharField(max_length=50)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES)
    vehicle_number = models.CharField(max_length=20)
    vehicle_model = models.CharField(max_length=100, blank=True)
    is_available = models.BooleanField(default=False)  # Changed default for approval process
    is_verified = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)
    current_latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_deliveries = models.PositiveIntegerField(default=0)
    verification_documents = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_drivers')

    def __str__(self):
        return f"{self.user.username} - {self.vehicle_type}"

    def update_location(self, latitude, longitude):
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.last_location_update = timezone.now()
        self.save()

    def approve(self, approved_by_user):
        self.is_available = True
        self.is_verified = True
        self.approved_at = timezone.now()
        self.approved_by = approved_by_user
        self.save()

class UserActivity(models.Model):
    ACTIVITY_TYPES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('profile_update', 'Profile Update'),
        ('password_change', 'Password Change'),
        ('order_placed', 'Order Placed'),
        ('order_updated', 'Order Updated'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'User Activities'

    def __str__(self):
        return f"{self.user.username} - {self.activity_type} at {self.created_at}"



class ContactMessage(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.subject}"