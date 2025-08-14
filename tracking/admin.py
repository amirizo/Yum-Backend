from django.contrib import admin
from .models import (
    DriverLocation, OrderTracking, LiveTracking, 
    TrackingEvent, Geofence, NotificationQueue
)

@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display = ('driver', 'latitude', 'longitude', 'accuracy', 'speed', 'timestamp')
    list_filter = ('timestamp', 'is_active')
    search_fields = ('driver__user__username',)
    readonly_fields = ('timestamp',)
    
    def has_add_permission(self, request):
        return False

@admin.register(OrderTracking)
class OrderTrackingAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'updated_by', 'timestamp')
    list_filter = ('status', 'timestamp')
    search_fields = ('order__order_number', 'message')
    readonly_fields = ('timestamp',)

@admin.register(LiveTracking)
class LiveTrackingAdmin(admin.ModelAdmin):
    list_display = ('order', 'driver', 'is_active', 'started_at', 'ended_at')
    list_filter = ('is_active', 'started_at')
    search_fields = ('order__order_number', 'driver__user__username')
    readonly_fields = ('session_id', 'started_at', 'ended_at')

@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ('live_tracking', 'event_type', 'description', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('description',)
    readonly_fields = ('timestamp',)

@admin.register(Geofence)
class GeofenceAdmin(admin.ModelAdmin):
    list_display = ('name', 'geofence_type', 'center_latitude', 'center_longitude', 'radius_meters', 'is_active')
    list_filter = ('geofence_type', 'is_active')
    search_fields = ('name',)

@admin.register(NotificationQueue)
class NotificationQueueAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_sent', 'created_at')
    list_filter = ('notification_type', 'recipient_type', 'is_sent', 'created_at')
    search_fields = ('recipient__username', 'title', 'message')
    readonly_fields = ('created_at', 'sent_at')
