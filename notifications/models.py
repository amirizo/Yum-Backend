from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import uuid
from django.utils import timezone

User = get_user_model()


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('order_created', 'Order Created'),
        ('order_confirmed', 'Order Confirmed'),
        ('order_assigned', 'Order Assigned'),
        ('driver_en_route', 'Driver En Route'),
        ('driver_arrived', 'Driver Arrived'),
        ('order_picked_up', 'Order Picked Up'),
        ('order_in_transit', 'Order In Transit'),
        ('order_delivered', 'Order Delivered'),
        ('order_cancelled', 'Order Cancelled'),
        ('payment_received', 'Payment Received'),
        ('rating_received', 'Rating Received'),
        ('system_alert', 'System Alert'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='sent_notifications')
    
    # Notification content
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')
    
    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Status and metadata
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Additional data as JSON
    extra_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient.get_full_name()}"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class NotificationPreference(models.Model):
    CHANNEL_CHOICES = [
        ('push', 'Push Notification'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('websocket', 'Real-time'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Channel preferences
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    websocket_enabled = models.BooleanField(default=True)
    
    # Notification type preferences
    order_updates = models.BooleanField(default=True)
    delivery_updates = models.BooleanField(default=True)
    payment_updates = models.BooleanField(default=True)
    promotional = models.BooleanField(default=False)
    system_alerts = models.BooleanField(default=True)
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_start_time = models.TimeField(null=True, blank=True)
    quiet_end_time = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.get_full_name()}"


class PushNotificationDevice(models.Model):
    DEVICE_TYPES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web Browser'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_devices')
    device_token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPES)
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'device_token']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.device_type}"


class RealTimeUpdate(models.Model):
    UPDATE_TYPES = [
        ('location', 'Location Update'),
        ('status', 'Status Update'),
        ('eta', 'ETA Update'),
        ('message', 'Message'),
        ('alert', 'Alert'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    update_type = models.CharField(max_length=20, choices=UPDATE_TYPES)
    
    # Related objects
    order_id = models.UUIDField(null=True, blank=True)
    dispatch_id = models.UUIDField(null=True, blank=True)
    user_id = models.IntegerField(null=True, blank=True)
    
    # Update data
    data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Delivery tracking
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['dispatch_id']),
            models.Index(fields=['user_id']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.update_type} - {self.timestamp}"
