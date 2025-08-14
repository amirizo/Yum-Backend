from django.contrib import admin
from .models import Dispatch, DispatchRoute, DispatchStatusHistory


@admin.register(Dispatch)
class DispatchAdmin(admin.ModelAdmin):
    list_display = ['order', 'driver', 'status', 'assigned_at', 'customer_rating']
    list_filter = ['status', 'assigned_at', 'customer_rating']
    search_fields = ['order__order_number', 'driver__email', 'dispatcher__email']
    readonly_fields = ['assigned_at']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('order', 'driver', 'dispatcher', 'route', 'assigned_at', 'accepted_at', 'status')
        }),
        ('Location Tracking', {
            'fields': ('current_latitude', 'current_longitude', 'last_location_update')
        }),
        ('Performance', {
            'fields': ('distance_traveled', 'time_to_pickup', 'time_to_delivery')
        }),
        ('Feedback', {
            'fields': ('driver_notes', 'customer_rating', 'customer_feedback')
        }),
        ('Status Timestamps', {
            'fields': ('en_route_pickup_at', 'arrived_pickup_at', 'picked_up_at',
                      'en_route_delivery_at', 'arrived_delivery_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DispatchRoute)
class DispatchRouteAdmin(admin.ModelAdmin):
    list_display = ['route_name', 'driver', 'status', 'total_distance', 'estimated_duration', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['route_name', 'driver__email', 'dispatcher__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DispatchStatusHistory)
class DispatchStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['dispatch', 'status', 'timestamp', 'created_by']
    list_filter = ['status', 'timestamp']
    search_fields = ['dispatch__order__order_number', 'created_by__email']
    readonly_fields = ['timestamp']
