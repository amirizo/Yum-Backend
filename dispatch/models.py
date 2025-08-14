from django.db import models
from django.contrib.auth import get_user_model
from orders.models import Order
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class DispatchRoute(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route_name = models.CharField(max_length=100)
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dispatch_routes')
    dispatcher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_routes')
    
    # Route details
    total_distance = models.FloatField(help_text="Total distance in kilometers")
    estimated_duration = models.IntegerField(help_text="Estimated duration in minutes")
    actual_duration = models.IntegerField(null=True, blank=True, help_text="Actual duration in minutes")
    
    # Status and timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Route optimization data
    optimization_score = models.FloatField(null=True, blank=True, help_text="Route efficiency score")
    fuel_estimate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['driver']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Route {self.route_name} - {self.driver.get_full_name()}"


class Dispatch(models.Model):
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('en_route_pickup', 'En Route to Pickup'),
        ('arrived_pickup', 'Arrived at Pickup'),
        ('picked_up', 'Picked Up'),
        ('en_route_delivery', 'En Route to Delivery'),
        ('arrived_delivery', 'Arrived at Delivery'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='dispatch')
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dispatches')
    dispatcher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_dispatches')
    route = models.ForeignKey(DispatchRoute, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatches')
    
    # Assignment details
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    
    # Tracking details
    current_latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)
    
    # Performance metrics
    distance_traveled = models.FloatField(null=True, blank=True, help_text="Distance in kilometers")
    time_to_pickup = models.IntegerField(null=True, blank=True, help_text="Time in minutes")
    time_to_delivery = models.IntegerField(null=True, blank=True, help_text="Time in minutes")
    
    # Driver notes and feedback
    driver_notes = models.TextField(blank=True)
    customer_rating = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    customer_feedback = models.TextField(blank=True)
    
    # Timestamps for status changes
    en_route_pickup_at = models.DateTimeField(null=True, blank=True)
    arrived_pickup_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    en_route_delivery_at = models.DateTimeField(null=True, blank=True)
    arrived_delivery_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['driver']),
            models.Index(fields=['status']),
            models.Index(fields=['assigned_at']),
        ]

    def __str__(self):
        return f"Dispatch {self.order.order_number} - {self.driver.get_full_name()}"


class DispatchStatusHistory(models.Model):
    dispatch = models.ForeignKey(Dispatch, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)
    location_latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    location_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "Dispatch status histories"

    def __str__(self):
        return f"{self.dispatch.order.order_number} - {self.status} at {self.timestamp}"
