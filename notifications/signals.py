from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from orders.models import Order
from dispatch.models import Dispatch
from .models import NotificationPreference
from .services import NotificationService

User = get_user_model()


@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """Create default notification preferences for new users"""
    if created:
        NotificationPreference.objects.create(user=instance)


@receiver(post_save, sender=Order)
def handle_order_notifications(sender, instance, created, **kwargs):
    """Handle notifications for order status changes"""
    if created:
        # Notify vendor about new order
        NotificationService.create_notification(
            recipient=instance.vendor,
            title="New Order Received",
            message=f"You have received a new order #{instance.order_number}",
            notification_type='order_created',
            content_object=instance
        )
        
        # Notify customer about order confirmation
        NotificationService.create_notification(
            recipient=instance.customer,
            title="Order Confirmed",
            message=f"Your order #{instance.order_number} has been confirmed",
            notification_type='order_confirmed',
            content_object=instance
        )


@receiver(pre_save, sender=Order)
def handle_order_status_change(sender, instance, **kwargs):
    """Handle notifications when order status changes"""
    if instance.pk:  # Only for existing orders
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                status_messages = {
                    'confirmed': 'Your order has been confirmed',
                    'preparing': 'Your order is being prepared',
                    'ready_for_pickup': 'Your order is ready for pickup',
                    'picked_up': 'Your order has been picked up',
                    'in_transit': 'Your order is on the way',
                    'delivered': 'Your order has been delivered',
                    'cancelled': 'Your order has been cancelled',
                }
                
                if instance.status in status_messages:
                    NotificationService.create_notification(
                        recipient=instance.customer,
                        title=f"Order {instance.order_number} Update",
                        message=status_messages[instance.status],
                        notification_type='order_updates',
                        content_object=instance
                    )
        except Order.DoesNotExist:
            pass


@receiver(post_save, sender=Dispatch)
def handle_dispatch_notifications(sender, instance, created, **kwargs):
    """Handle notifications for dispatch assignments"""
    if created:
        # Notify driver about new assignment
        NotificationService.create_notification(
            recipient=instance.driver,
            title="New Delivery Assignment",
            message=f"You have been assigned order #{instance.order.order_number}",
            notification_type='order_assigned',
            content_object=instance.order
        )
        
        # Notify customer about driver assignment
        NotificationService.create_notification(
            recipient=instance.order.customer,
            title="Driver Assigned",
            message=f"A driver has been assigned to your order #{instance.order.order_number}",
            notification_type='order_assigned',
            content_object=instance.order
        )
