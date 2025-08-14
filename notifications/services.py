from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.contenttypes.models import ContentType
from .models import Notification, NotificationPreference
import json


class NotificationService:
    @staticmethod
    def create_notification(recipient, title, message, notification_type, 
                          priority='normal', sender=None, content_object=None, 
                          extra_data=None):
        """Create a new notification"""
        notification_data = {
            'recipient': recipient,
            'title': title,
            'message': message,
            'notification_type': notification_type,
            'priority': priority,
            'sender': sender,
            'extra_data': extra_data or {}
        }
        
        if content_object:
            notification_data['content_type'] = ContentType.objects.get_for_model(content_object)
            notification_data['object_id'] = content_object.pk
        
        notification = Notification.objects.create(**notification_data)
        
        # Send notification through various channels
        NotificationService.send_notification(notification)
        
        return notification

    @staticmethod
    def send_notification(notification):
        """Send notification through enabled channels"""
        try:
            preferences = NotificationPreference.objects.get(user=notification.recipient)
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            preferences = NotificationPreference.objects.create(user=notification.recipient)
        
        # Check if notification type is enabled
        if not NotificationService._is_notification_enabled(notification, preferences):
            return
        
        # Send via WebSocket if enabled
        if preferences.websocket_enabled:
            NotificationService._send_websocket_notification(notification)
        
        # Send via push notification if enabled
        if preferences.push_enabled:
            NotificationService._send_push_notification(notification)
        
        # Send via email if enabled
        if preferences.email_enabled:
            NotificationService._send_email_notification(notification)
        
        # Mark as sent
        notification.is_sent = True
        notification.save()

    @staticmethod
    def _is_notification_enabled(notification, preferences):
        """Check if notification type is enabled in user preferences"""
        type_mapping = {
            'order_created': preferences.order_updates,
            'order_confirmed': preferences.order_updates,
            'order_assigned': preferences.delivery_updates,
            'driver_en_route': preferences.delivery_updates,
            'driver_arrived': preferences.delivery_updates,
            'order_picked_up': preferences.delivery_updates,
            'order_in_transit': preferences.delivery_updates,
            'order_delivered': preferences.delivery_updates,
            'order_cancelled': preferences.order_updates,
            'payment_received': preferences.payment_updates,
            'rating_received': preferences.order_updates,
            'system_alert': preferences.system_alerts,
        }
        
        return type_mapping.get(notification.notification_type, True)

    @staticmethod
    def _send_websocket_notification(notification):
        """Send notification via WebSocket"""
        channel_layer = get_channel_layer()
        
        notification_data = {
            'id': str(notification.id),
            'title': notification.title,
            'message': notification.message,
            'notification_type': notification.notification_type,
            'priority': notification.priority,
            'created_at': notification.created_at.isoformat(),
            'extra_data': notification.extra_data
        }
        
        # Send to user-specific group
        async_to_sync(channel_layer.group_send)(
            f"user_{notification.recipient.id}",
            {
                'type': 'notification_message',
                'notification': notification_data
            }
        )

    @staticmethod
    def _send_push_notification(notification):
        """Send push notification to user's devices"""
        from .models import PushNotificationDevice
        
        devices = PushNotificationDevice.objects.filter(
            user=notification.recipient,
            is_active=True
        )
        
        for device in devices:
            # Here you would integrate with FCM, APNs, or other push services
            # For now, we'll just log it
            print(f"Sending push notification to {device.device_token}: {notification.title}")

    @staticmethod
    def _send_email_notification(notification):
        """Send email notification"""
        # Here you would integrate with email service
        # For now, we'll just log it
        print(f"Sending email to {notification.recipient.email}: {notification.title}")

    @staticmethod
    def broadcast_location_update(dispatch, latitude, longitude):
        """Broadcast location update to relevant users"""
        channel_layer = get_channel_layer()
        
        update_data = {
            'dispatch_id': str(dispatch.id),
            'order_id': str(dispatch.order.id),
            'latitude': str(latitude),
            'longitude': str(longitude),
            'driver_name': dispatch.driver.get_full_name(),
            'timestamp': dispatch.last_location_update.isoformat() if dispatch.last_location_update else None
        }
        
        # Send to order tracking room
        async_to_sync(channel_layer.group_send)(
            f"tracking_{dispatch.order.id}",
            {
                'type': 'tracking_update',
                'data': update_data
            }
        )
        
        # Send to customer
        async_to_sync(channel_layer.group_send)(
            f"user_{dispatch.order.customer.id}",
            {
                'type': 'location_update',
                'dispatch_id': str(dispatch.id),
                'latitude': str(latitude),
                'longitude': str(longitude),
                'timestamp': update_data['timestamp']
            }
        )

    @staticmethod
    def broadcast_status_update(dispatch, status):
        """Broadcast status update to relevant users"""
        channel_layer = get_channel_layer()
        
        # Send to order tracking room
        async_to_sync(channel_layer.group_send)(
            f"tracking_{dispatch.order.id}",
            {
                'type': 'tracking_update',
                'data': {
                    'dispatch_id': str(dispatch.id),
                    'order_id': str(dispatch.order.id),
                    'status': status,
                    'driver_name': dispatch.driver.get_full_name()
                }
            }
        )
        
        # Create notifications for status changes
        status_messages = {
            'accepted': 'Your order has been accepted by the driver',
            'en_route_pickup': 'Driver is on the way to pickup location',
            'arrived_pickup': 'Driver has arrived at pickup location',
            'picked_up': 'Your order has been picked up',
            'en_route_delivery': 'Your order is on the way',
            'arrived_delivery': 'Driver has arrived at delivery location',
            'delivered': 'Your order has been delivered successfully',
        }
        
        if status in status_messages:
            # Notify customer
            NotificationService.create_notification(
                recipient=dispatch.order.customer,
                title=f"Order {dispatch.order.order_number} Update",
                message=status_messages[status],
                notification_type='delivery_updates',
                content_object=dispatch.order
            )
            
            # Notify vendor for certain statuses
            if status in ['picked_up', 'delivered']:
                NotificationService.create_notification(
                    recipient=dispatch.order.vendor,
                    title=f"Order {dispatch.order.order_number} Update",
                    message=status_messages[status],
                    notification_type='order_updates',
                    content_object=dispatch.order
                )
