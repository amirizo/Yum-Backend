from django.db import models
from django.utils import timezone
from authentication.models import User, Driver
from orders.models import Order
import uuid

class DriverLocation(models.Model):
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='location_history')
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    accuracy = models.FloatField(help_text='GPS accuracy in meters')
    speed = models.FloatField(null=True, blank=True, help_text='Speed in km/h')
    heading = models.FloatField(null=True, blank=True, help_text='Direction in degrees')
    altitude = models.FloatField(null=True, blank=True, help_text='Altitude in meters')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['driver', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.driver.user.username} - {self.timestamp}"

class OrderTracking(models.Model):
    TRACKING_STATUS_CHOICES = (
        ('order_placed', 'Order Placed'),
        ('order_confirmed', 'Order Confirmed'),
        ('preparing', 'Preparing Order'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('driver_assigned', 'Driver Assigned'),
        ('driver_en_route_pickup', 'Driver En Route to Pickup'),
        ('driver_arrived_pickup', 'Driver Arrived at Pickup'),
        ('order_picked_up', 'Order Picked Up'),
        ('en_route_delivery', 'En Route to Delivery'),
        ('driver_arrived_delivery', 'Driver Arrived at Delivery'),
        ('order_delivered', 'Order Delivered'),
        ('order_cancelled', 'Order Cancelled'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tracking_updates')
    status = models.CharField(max_length=30, choices=TRACKING_STATUS_CHOICES)
    message = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Order {self.order.order_number} - {self.status}"

class LiveTracking(models.Model):
    """Real-time tracking session for active deliveries"""
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='live_tracking')
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE)
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # Current tracking data
    current_latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    last_update = models.DateTimeField(null=True, blank=True)
    
    # Estimated times
    estimated_pickup_arrival = models.DateTimeField(null=True, blank=True)
    estimated_delivery_arrival = models.DateTimeField(null=True, blank=True)
    
    # Distance tracking
    total_distance_covered = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    distance_to_pickup = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    distance_to_delivery = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Live Tracking - Order {self.order.order_number}"

    def end_session(self):
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()

class TrackingEvent(models.Model):
    EVENT_TYPES = (
        ('location_update', 'Location Update'),
        ('status_change', 'Status Change'),
        ('geofence_enter', 'Geofence Enter'),
        ('geofence_exit', 'Geofence Exit'),
        ('speed_alert', 'Speed Alert'),
        ('route_deviation', 'Route Deviation'),
        ('emergency_alert', 'Emergency Alert'),
    )

    live_tracking = models.ForeignKey(LiveTracking, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField()
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.event_type} - {self.timestamp}"

class Geofence(models.Model):
    GEOFENCE_TYPES = (
        ('pickup', 'Pickup Location'),
        ('delivery', 'Delivery Location'),
        ('vendor', 'Vendor Location'),
        ('warehouse', 'Warehouse'),
        ('restricted', 'Restricted Area'),
    )

    name = models.CharField(max_length=100)
    geofence_type = models.CharField(max_length=20, choices=GEOFENCE_TYPES)
    center_latitude = models.DecimalField(max_digits=10, decimal_places=8)
    center_longitude = models.DecimalField(max_digits=11, decimal_places=8)
    radius_meters = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} ({self.geofence_type})"

    def is_point_inside(self, latitude, longitude):
        """Check if a point is inside this geofence"""
        from .services import TrackingService
        tracking_service = TrackingService()
        distance = tracking_service.calculate_distance(
            float(self.center_latitude), float(self.center_longitude),
            float(latitude), float(longitude)
        )
        return distance * 1000 <= self.radius_meters  # Convert km to meters

class NotificationQueue(models.Model):
    NOTIFICATION_TYPES = (
        ('order_update', 'Order Update'),
        ('driver_assigned', 'Driver Assigned'),
        ('pickup_ready', 'Pickup Ready'),
        ('en_route', 'En Route'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('emergency', 'Emergency'),
    )

    RECIPIENT_TYPES = (
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('driver', 'Driver'),
        ('admin', 'Admin'),
    )

    recipient = models.ForeignKey(User, on_delete=models.CASCADE)
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_TYPES)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} to {self.recipient.username}"
