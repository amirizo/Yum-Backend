from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from orders.models import Order
from dispatch.models import Dispatch
from .models import NotificationPreference
from .services import NotificationService
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """Create default notification preferences for new users"""
    if created:
        NotificationPreference.objects.create(user=instance)


@receiver(post_save, sender=Order)
def handle_order_creation(sender, instance, created, **kwargs):
    """Handle notifications when a new order is created"""
    if created:
        try:
            # Send comprehensive notifications for new order
            NotificationService.send_order_status_notification(instance)
        except Exception as e:
            logger.error(f"Error sending order creation notifications: {str(e)}")


@receiver(pre_save, sender=Order)
def handle_order_status_change(sender, instance, **kwargs):
    """Handle notifications when order status changes"""
    if instance.pk:  # Only for existing orders
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Send comprehensive notifications for status change
                NotificationService.send_order_status_notification(instance, old_instance.status)
                
                # Log the status change
                logger.info(f"Order {instance.order_number} status changed from {old_instance.status} to {instance.status}")
                
        except Order.DoesNotExist:
            logger.warning(f"Order {instance.pk} not found in pre_save signal")
        except Exception as e:
            logger.error(f"Error handling order status change: {str(e)}")


@receiver(post_save, sender=Dispatch)
def handle_dispatch_notifications(sender, instance, created, **kwargs):
    """Handle notifications for dispatch assignments"""
    if created:
        try:
            # Update order status to picked_up when dispatch is created
            if instance.order.status != 'picked_up':
                instance.order.status = 'picked_up'
                instance.order.save()
            
            # The order status change will trigger the comprehensive notification system
            # through the order pre_save signal
            
        except Exception as e:
            logger.error(f"Error handling dispatch creation: {str(e)}")


@receiver(pre_save, sender=Dispatch)
def handle_dispatch_status_change(sender, instance, **kwargs):
    """Handle notifications when dispatch status changes"""
    if instance.pk:  # Only for existing dispatches
        try:
            old_instance = Dispatch.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Map dispatch status to order status and update order accordingly
                dispatch_to_order_status = {
                    'accepted': 'picked_up',
                    'en_route_pickup': 'picked_up',
                    'arrived_pickup': 'picked_up',
                    'picked_up': 'picked_up',
                    'en_route_delivery': 'in_transit',
                    'arrived_delivery': 'in_transit',
                    'delivered': 'delivered',
                }
                
                if instance.status in dispatch_to_order_status:
                    new_order_status = dispatch_to_order_status[instance.status]
                    if instance.order.status != new_order_status:
                        instance.order.status = new_order_status
                        instance.order.save()
                        # This will trigger the order status change notification
                
                # Log the dispatch status change
                logger.info(f"Dispatch {instance.id} status changed from {old_instance.status} to {instance.status}")
                
        except Dispatch.DoesNotExist:
            logger.warning(f"Dispatch {instance.pk} not found in pre_save signal")
        except Exception as e:
            logger.error(f"Error handling dispatch status change: {str(e)}")
