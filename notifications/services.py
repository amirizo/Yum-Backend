from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.contenttypes.models import ContentType
from .models import Notification, NotificationPreference
from django.contrib.auth import get_user_model
from django.utils import timezone
import json
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


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
            notification_data['object_id'] = str(content_object.pk)  # Convert to string to avoid SQLite integer overflow
        
        notification = Notification.objects.create(**notification_data)
        
        # Send notification through various channels
        NotificationService.send_notification(notification)
        
        return notification

    @staticmethod
    def send_order_status_notification(order, old_status=None):
        """Send comprehensive notifications for order status changes"""
        status = order.status
        order_number = order.order_number
        
        # Define notification content for each status
        notification_config = {
            'pending': {
                'customer': {
                    'title': f"Order {order_number} Created",
                    'message': f"Your order has been created and is pending confirmation from {order.vendor.business_name}.",
                    'type': 'order_created'
                },
                'vendor': {
                    'title': f"New Order Received - {order_number}",
                    'message': f"You have received a new order from {order.customer.get_full_name()}. Please review and confirm.",
                    'type': 'order_created'
                }
            },
            'confirmed': {
                'customer': {
                    'title': f"Order {order_number} Confirmed",
                    'message': f"Great news! {order.vendor.business_name} has confirmed your order and will start preparing it soon.",
                    'type': 'order_confirmed'
                },
                'vendor': {
                    'title': f"Order {order_number} Confirmed",
                    'message': f"Order has been confirmed. Please start preparing the items.",
                    'type': 'order_confirmed'
                }
            },
            'preparing': {
                'customer': {
                    'title': f"Order {order_number} Being Prepared",
                    'message': f"Your order is now being prepared by {order.vendor.business_name}. We'll notify you when it's ready!",
                    'type': 'order_preparing'
                },
                'vendor': {
                    'title': f"Order {order_number} - Preparation Started",
                    'message': f"Order preparation has been marked as started.",
                    'type': 'order_preparing'
                }
            },
            'ready': {
                'customer': {
                    'title': f"Order {order_number} Ready for Pickup",
                    'message': f"Your order is ready! We're looking for a driver to pick it up and deliver it to you.",
                    'type': 'order_ready'
                },
                'vendor': {
                    'title': f"Order {order_number} Ready",
                    'message': f"Order is ready for pickup. Drivers have been notified.",
                    'type': 'order_ready'
                },
                'drivers': {
                    'title': f"New Order Available - {order_number}",
                    'message': f"Order ready for pickup from {order.vendor.business_name}. Tap to accept!",
                    'type': 'order_available'
                }
            },
            'picked_up': {
                'customer': {
                    'title': f"Order {order_number} Picked Up",
                    'message': f"Your order has been picked up by {order.driver.user.get_full_name() if order.driver and hasattr(order.driver, 'user') else 'our driver'} and is on the way to you!",
                    'type': 'order_picked_up'
                },
                'vendor': {
                    'title': f"Order {order_number} Picked Up",
                    'message': f"Order has been picked up by the driver.",
                    'type': 'order_picked_up'
                },
                'driver': {
                'title': f"Order {order_number} Assignment",
                'message': f"You have successfully picked up the order. Please deliver to customer.",
                'type': 'order_assigned'
            }
            },
            'in_transit': {
                'customer': {
                    'title': f"Order {order_number} On The Way",
                    'message': f"Your order is currently being delivered to you. Track your driver's location in real-time!",
                    'type': 'driver_en_route'
                },
                'vendor': {
                    'title': f"Order {order_number} In Transit",
                    'message': f"Order is currently being delivered to the customer.",
                    'type': 'order_in_transit'
                }
            },
            'delivered': {
                'customer': {
                    'title': f"Order {order_number} Delivered!",
                    'message': f"Your order has been successfully delivered! Thank you for choosing us. Please rate your experience.",
                    'type': 'order_delivered'
                },
                'vendor': {
                    'title': f"Order {order_number} Delivered",
                    'message': f"Order has been successfully delivered to the customer.",
                    'type': 'order_delivered'
                },
                'driver': {
                    'title': f"Order {order_number} Delivered",
                    'message': f"Order has been marked as delivered. Great job!",
                    'type': 'order_delivered'
                }
            },
            'cancelled': {
                'customer': {
                    'title': f"Order {order_number} Cancelled",
                    'message': f"Your order has been cancelled. If payment was made, a refund will be processed within 3-5 business days.",
                    'type': 'order_cancelled'
                },
                'vendor': {
                    'title': f"Order {order_number} Cancelled",
                    'message': f"Order has been cancelled.",
                    'type': 'order_cancelled'
                }
            }
        }
        
        # Send notifications based on status
        if status in notification_config:
            config = notification_config[status]
            
            # Send to customer
            if 'customer' in config:
                NotificationService.create_notification(
                    recipient=order.customer,
                    title=config['customer']['title'],
                    message=config['customer']['message'],
                    notification_type=config['customer']['type'],
                    priority='normal',
                    content_object=order,
                    extra_data={'order_id': str(order.id), 'status': status}
                )
            
            # Send to vendor
            if 'vendor' in config and hasattr(order.vendor, 'user'):
                NotificationService.create_notification(
                    recipient=order.vendor.user,
                    title=config['vendor']['title'],
                    message=config['vendor']['message'],
                    notification_type=config['vendor']['type'],
                    priority='normal',
                    content_object=order,
                    extra_data={'order_id': str(order.id), 'status': status}
                )
            
            # Send to driver (if assigned)
            if 'driver' in config and order.driver and hasattr(order.driver, 'user'):
                NotificationService.create_notification(
                    recipient=order.driver.user,
                    title=config['driver']['title'],
                    message=config['driver']['message'],
                    notification_type=config['driver']['type'],
                    priority='normal',
                    content_object=order,
                    extra_data={'order_id': str(order.id), 'status': status}
                )
            
            # Send to all available drivers (for ready status)
            if 'drivers' in config and status == 'ready':
                NotificationService.notify_available_drivers(order, config['drivers'])
        
        # Send real-time updates via WebSocket
        NotificationService.broadcast_order_status_update(order, old_status)

    @staticmethod
    def notify_available_drivers(order, driver_config):
        """Notify all available drivers about a new order"""
        try:
            from authentication.models import Driver
            
            # Get all active drivers
            available_drivers = Driver.objects.filter(
                user__is_active=True,
                is_available=True
            ).select_related('user')
            
            for driver in available_drivers:
                if hasattr(driver, 'user'):
                    NotificationService.create_notification(
                        recipient=driver.user,
                        title=driver_config['title'],
                        message=driver_config['message'],
                        notification_type=driver_config['type'],
                        priority='high',
                        content_object=order,
                        extra_data={
                            'order_id': str(order.id),
                            'vendor_name': order.vendor.business_name,
                            'vendor_address': order.vendor.business_address,
                            'customer_address': order.delivery_address_text,
                            'total_amount': str(order.total_amount),
                            'estimated_delivery_time': order.estimated_delivery_time.isoformat() if order.estimated_delivery_time else None
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Error notifying drivers: {str(e)}")

    @staticmethod
    def broadcast_order_status_update(order, old_status=None):
        """Broadcast order status update via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            
            update_data = {
                'order_id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
                'old_status': old_status,
                'vendor_name': order.vendor.business_name,
                'estimated_delivery_time': order.estimated_delivery_time.isoformat() if order.estimated_delivery_time else None,
                'timestamp': order.updated_at.isoformat()
            }
            
            # Send to order-specific room
            async_to_sync(channel_layer.group_send)(
                f"order_{order.id}",
                {
                    'type': 'order_status_update',
                    'data': update_data
                }
            )
            
            # Send to customer's personal channel
            async_to_sync(channel_layer.group_send)(
                f"user_{order.customer.id}",
                {
                    'type': 'order_update',
                    'order_id': str(order.id),
                    'status': order.status,
                    'data': update_data
                }
            )
            
            # Send to vendor's personal channel
            if hasattr(order.vendor, 'user'):
                async_to_sync(channel_layer.group_send)(
                    f"user_{order.vendor.user.id}",
                    {
                        'type': 'order_update',
                        'order_id': str(order.id),
                        'status': order.status,
                        'data': update_data
                    }
                )
            
            # Send to driver's personal channel (if assigned)
            if order.driver and hasattr(order.driver, 'user'):
                async_to_sync(channel_layer.group_send)(
                    f"user_{order.driver.user.id}",
                    {
                        'type': 'order_update',
                        'order_id': str(order.id),
                        'status': order.status,
                        'data': update_data
                    }
                )
            
            # Send to all drivers if order is ready
            if order.status == 'ready':
                async_to_sync(channel_layer.group_send)(
                    "drivers",
                    {
                        'type': 'new_order_available',
                        'order_id': str(order.id),
                        'data': update_data
                    }
                )
                
        except Exception as e:
            logger.error(f"Error broadcasting order status update: {str(e)}")

    @staticmethod
    def send_driver_location_update(order, latitude, longitude, driver):
        """Send real-time location updates to customer and vendor"""
        try:
            channel_layer = get_channel_layer()
            
            location_data = {
                'order_id': str(order.id),
                'driver_id': str(driver.id),
                'driver_name': driver.user.get_full_name() if hasattr(driver, 'user') else 'Driver',
                'latitude': str(latitude),
                'longitude': str(longitude),
                'timestamp': timezone.now().isoformat()
            }
            
            # Send to order tracking room
            async_to_sync(channel_layer.group_send)(
                f"tracking_{order.id}",
                {
                    'type': 'location_update',
                    'data': location_data
                }
            )
            
            # Send to customer
            async_to_sync(channel_layer.group_send)(
                f"user_{order.customer.id}",
                {
                    'type': 'driver_location_update',
                    'data': location_data
                }
            )
            
        except Exception as e:
            logger.error(f"Error sending location update: {str(e)}")

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
            'order_preparing': preferences.order_updates,
            'order_ready': preferences.order_updates,
            'order_available': preferences.delivery_updates,
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
            logger.info(f"Sending push notification to {device.device_token}: {notification.title}")

    @staticmethod
    def _send_email_notification(notification):
        """Send email notification"""
        # Here you would integrate with email service
        # For now, we'll just log it
        logger.info(f"Sending email to {notification.recipient.email}: {notification.title}")

    @staticmethod
    def broadcast_location_update(dispatch, latitude, longitude):
        """Broadcast location update to relevant users (legacy method for backward compatibility)"""
        try:
            from dispatch.models import Dispatch
            
            update_data = {
                'dispatch_id': str(dispatch.id),
                'order_id': str(dispatch.order.id),
                'latitude': str(latitude),
                'longitude': str(longitude),
                'driver_name': dispatch.driver.get_full_name(),
                'timestamp': dispatch.last_location_update.isoformat() if dispatch.last_location_update else None
            }
            
            channel_layer = get_channel_layer()
            
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
        except Exception as e:
            logger.error(f"Error broadcasting location update: {str(e)}")

    @staticmethod
    def broadcast_status_update(dispatch, status):
        """Broadcast status update to relevant users (legacy method for backward compatibility)"""
        try:
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
            
            # Create notifications for status changes using the new comprehensive system
            NotificationService.send_order_status_notification(dispatch.order)
            
        except Exception as e:
            logger.error(f"Error broadcasting status update: {str(e)}")
