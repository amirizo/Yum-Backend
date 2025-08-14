from django.contrib import admin
from .models import Notification, NotificationPreference, PushNotificationDevice, RealTimeUpdate


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'notification_type', 'priority', 'is_read', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'recipient__email']
    readonly_fields = ['created_at', 'read_at']
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('recipient', 'sender', 'title', 'message', 'notification_type', 'priority')
        }),
        ('Content Object', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read', 'is_sent', 'read_at')
        }),
        ('Additional Data', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'push_enabled', 'email_enabled', 'sms_enabled', 'websocket_enabled']
    list_filter = ['push_enabled', 'email_enabled', 'sms_enabled', 'websocket_enabled']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']


@admin.register(PushNotificationDevice)
class PushNotificationDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_type', 'device_name', 'is_active', 'last_used']
    list_filter = ['device_type', 'is_active', 'created_at']
    search_fields = ['user__email', 'device_name', 'device_token']


@admin.register(RealTimeUpdate)
class RealTimeUpdateAdmin(admin.ModelAdmin):
    list_display = ['update_type', 'order_id', 'dispatch_id', 'timestamp', 'is_delivered']
    list_filter = ['update_type', 'is_delivered', 'timestamp']
    search_fields = ['order_id', 'dispatch_id']
    readonly_fields = ['timestamp']
