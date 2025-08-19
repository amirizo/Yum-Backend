from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from authentication.services import SMSService
import logging

logger = logging.getLogger(__name__)

class OrderNotificationService:
    @staticmethod
    def send_order_accepted_email(order):
        """Send email to customer when vendor accepts order"""
        try:
            vendor_user = getattr(order.vendor, 'user', None)
            context = {
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'order_number': order.order_number,
                'vendor_name': f"{vendor_user.first_name} {vendor_user.last_name}" if vendor_user else order.vendor.business_name,
                'estimated_time': order.estimated_delivery_time,
                'total_amount': order.total_amount,
                'order_items': order.items.all(),
                'delivery_address': order.delivery_address,
            }
            
            subject = f"Order #{order.order_number} Confirmed - YumExpress"
            html_message = render_to_string('emails/order_accepted.html', context)
            plain_message = render_to_string('emails/order_accepted.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.customer.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Order accepted email sent to {order.customer.email} for order {order.order_number}")
        except Exception as e:
            logger.error(f"Failed to send order accepted email: {str(e)}")

    @staticmethod
    def send_order_picked_up_email(order):
        """Send email to customer when driver picks up order"""
        try:
            driver_user = getattr(order.driver, 'user', None)
            context = {
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'order_number': order.order_number,
                'driver_name': f"{driver_user.first_name} {driver_user.last_name}" if driver_user else "Driver",
                'driver_phone': driver_user.phone_number if driver_user else "",
                'estimated_delivery': order.estimated_delivery_time,
                'delivery_address': order.delivery_address,
            }
            
            subject = f"Order #{order.order_number} Picked Up - YumExpress"
            html_message = render_to_string('emails/order_picked_up.html', context)
            plain_message = render_to_string('emails/order_picked_up.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.customer.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Order picked up email sent to {order.customer.email} for order {order.order_number}")
        except Exception as e:
            logger.error(f"Failed to send order picked up email: {str(e)}")

    @staticmethod
    def send_order_rejected_email(order, rejection_reason=""):
        """Send email to customer when vendor rejects order"""
        try:
            vendor_user = getattr(order.vendor, 'user', None)
            context = {
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'order_number': order.order_number,
                'vendor_name': f"{vendor_user.first_name} {vendor_user.last_name}" if vendor_user else order.vendor.business_name,
                'rejection_reason': rejection_reason,
                'refund_amount': order.total_amount,
                'refund_timeline': "1 business days",
            }
            
            subject = f"Order #{order.order_number} Update - YumExpress"
            html_message = render_to_string('emails/order_rejected.html', context)
            plain_message = render_to_string('emails/order_rejected.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.customer.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Order rejected email sent to {order.customer.email} for order {order.order_number}")
        except Exception as e:
            logger.error(f"Failed to send order rejected email: {str(e)}")

    @staticmethod
    def send_order_rejection_admin_email(order, rejection_reason=""):
        """Send email to admin when vendor rejects order"""
        try:
            vendor_user = getattr(order.vendor, 'user', None)
            context = {
                'order_number': order.order_number,
                'vendor_name': f"{vendor_user.first_name} {vendor_user.last_name}" if vendor_user else order.vendor.business_name,
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'customer_email': order.customer.email,
                'customer_phone': order.customer.phone_number,
                'delivery_address': order.delivery_address,
                'rejection_reason': rejection_reason,
                'total_amount': order.total_amount,
            }
            
            subject = f"Order #{order.order_number} Rejected by Vendor - YumExpress"
            html_message = render_to_string('emails/order_rejected_admin.html', context)
            plain_message = render_to_string('emails/order_rejected_admin.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL_DEFAULT],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Order rejection email sent to admin for order {order.order_number}")
        except Exception as e:
            logger.error(f"Failed to send order rejection email to admin: {str(e)}")

    @staticmethod
    def process_order_rejection(order, rejection_reason="", rejected_by=None):
        """Handle complete order rejection workflow"""
        try:
            # Update order status
            order.status = 'cancelled'
            order.payment_status = 'refunded'
            order.save()
            
            # Create status history
            from .models import OrderStatusHistory
            OrderStatusHistory.objects.create(
                order=order,
                status='cancelled',
                changed_by=rejected_by or order.vendor,
                notes=f"Order rejected by vendor. Reason: {rejection_reason}"
            )
            
            # Process refund (integrate with payment gateway)
            OrderNotificationService.process_refund(order)
            
            # Send notification email
            OrderNotificationService.send_order_rejected_email(order, rejection_reason)
            
            # Send SMS notification
            sms_message = f"Your order #{order.order_number} has been cancelled. Refund of TZS {order.total_amount} will be processed within 1 business days."
            SMSService.send_sms(order.customer.phone_number, sms_message)
            
            logger.info(f"Order {order.order_number} rejection processed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process order rejection: {str(e)}")
            return False

    @staticmethod
    def process_refund(order):
        """Process refund through payment gateway"""
        try:
            # Import payment service
            from payments.services import ClickPesaService
            
            # Get the original payment transaction
            from payments.models import Payment
            payment = Payment.objects.filter(order=order, status='completed').first()
            
            if payment:
                clickpesa_service = ClickPesaService()
                refund_result = clickpesa_service.process_refund(
                    payment_id=payment.clickpesa_payment_id,
                    amount=float(order.total_amount),
                    reason="Order cancelled by vendor"
                )
                
                if refund_result.get('success'):
                    # Create refund record
                    from payments.models import Refund
                    Refund.objects.create(
                        payment=payment,
                        amount=order.total_amount,
                        reason="Order cancelled by vendor",
                        status='completed',
                        clickpesa_refund_id=refund_result.get('refund_id')
                    )
                    logger.info(f"Refund processed for order {order.order_number}")
                else:
                    logger.error(f"Refund failed for order {order.order_number}: {refund_result.get('error')}")
            
        except Exception as e:
            logger.error(f"Failed to process refund for order {order.order_number}: {str(e)}")

    @staticmethod
    def send_order_delivered_email(order):
        """Send thank you email to customer when order is delivered"""
        try:
            driver_user = getattr(order.driver, 'user', None)
            vendor_user = getattr(order.vendor, 'user', None)
            
            context = {
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'order_number': order.order_number,
                'vendor_name': f"{vendor_user.first_name} {vendor_user.last_name}" if vendor_user else order.vendor.business_name,
                'driver_name': f"{driver_user.first_name} {driver_user.last_name}" if driver_user else "Driver",
                'delivery_time': order.actual_delivery_time or timezone.now(),
                'total_amount': order.total_amount,
                'order_items': order.items.all(),
                'delivery_address': order.delivery_address,
            }
            
            subject = f"Order #{order.order_number} Delivered - Thank You! - YumExpress"
            html_message = render_to_string('emails/order_delivered.html', context)
            plain_message = render_to_string('emails/order_delivered.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.customer.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Order delivered email sent to {order.customer.email} for order {order.order_number}")
            
            # Send SMS notification
            sms_message = f"Your order #{order.order_number} has been delivered! Thank you for choosing YumExpress. Total: TZS {order.total_amount:,.0f}"
            SMSService.send_sms(order.customer.phone_number, sms_message)
            
        except Exception as e:
            logger.error(f"Failed to send order delivered email: {str(e)}")

    @staticmethod
    def notify_vendor_order_delivered(order):
        """Notify vendor when order is delivered"""
        try:
            vendor_user = getattr(order.vendor, 'user', None)
            if not vendor_user:
                return
                
            driver_user = getattr(order.driver, 'user', None)
            
            context = {
                'vendor_name': f"{vendor_user.first_name} {vendor_user.last_name}",
                'order_number': order.order_number,
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'driver_name': f"{driver_user.first_name} {driver_user.last_name}" if driver_user else "Driver",
                'delivery_time': order.actual_delivery_time or timezone.now(),
                'total_amount': order.total_amount,
            }
            
            subject = f"Order #{order.order_number} Successfully Delivered - YumExpress"
            html_message = render_to_string('emails/vendor_order_delivered.html', context)
            plain_message = render_to_string('emails/vendor_order_delivered.txt', context)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[vendor_user.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Vendor delivery notification sent to {vendor_user.email} for order {order.order_number}")
            
        except Exception as e:
            logger.error(f"Failed to send vendor delivery notification: {str(e)}")

    @staticmethod
    def notify_all_drivers_new_order(order):
        """Notify all available drivers when order is ready for pickup"""
        try:
            from django.contrib.auth import get_user_model
            from authentication.services import SMSService
            
            User = get_user_model()
            
            # Get all active drivers
            drivers = User.objects.filter(
                user_type='driver', 
                is_active=True,
                driver_profile__is_available=True
            )
            
            vendor_user = getattr(order.vendor, 'user', None)
            vendor_location = order.vendor.primary_location
            
            for driver in drivers:
                try:
                    # Send SMS notification
                    sms_message = (
                        f"New order available! Order #{order.order_number} "
                        f"from {order.vendor.business_name}. "
                        f"Value: TZS {order.total_amount:,.0f}. "
                        f"Pickup: {vendor_location.address if vendor_location else 'N/A'}. "
                        f"Reply to accept."
                    )
                    SMSService.send_sms(driver.phone_number, sms_message)
                    
                    # Send email notification
                    context = {
                        'driver_name': f"{driver.first_name} {driver.last_name}",
                        'order_number': order.order_number,
                        'vendor_name': order.vendor.business_name,
                        'vendor_location': vendor_location.address if vendor_location else 'N/A',
                        'customer_address': order.delivery_address_text,
                        'total_amount': order.total_amount,
                        'estimated_delivery': order.estimated_delivery_time,
                        'pickup_instructions': getattr(order, 'pickup_instructions', ''),
                    }
                    
                    subject = f"New Delivery Available - Order #{order.order_number} - YumExpress"
                    html_message = render_to_string('emails/driver_new_order.html', context)
                    plain_message = render_to_string('emails/driver_new_order.txt', context)
                    
                    send_mail(
                        subject=subject,
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[driver.email],
                        html_message=html_message,
                        fail_silently=True,  # Don't fail if one email fails
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to notify driver {driver.id}: {str(e)}")
                    continue
            
            logger.info(f"Notified {drivers.count()} drivers about order {order.order_number}")
            
        except Exception as e:
            logger.error(f"Failed to notify drivers about order {order.order_number}: {str(e)}")


    @staticmethod
    def send_order_status_update_email(order, old_status, new_status, notes=""):
        try:
            status_messages = {
                'preparing': 'Your order is being prepared',
                'ready': 'Your order is ready for pickup',
                'picked_up': 'Your order has been picked up by our driver',
                'in_transit': 'Your order is on the way',
                'delivered': 'Your order has been delivered',
            }

            context = {
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'order_number': order.order_number,
                'old_status': old_status.replace('_', ' ').title(),
                'new_status': new_status.replace('_', ' ').title(),
                'status_message': status_messages.get(new_status, f'Order status updated to {new_status}'),
                'notes': notes,
                'estimated_delivery': order.estimated_delivery_time,
            }

            # Extra context if picked up or in transit
            if new_status in ['picked_up', 'in_transit']:
                driver = getattr(order, "driver", None)
                delivery_address = getattr(order, "delivery_address", None)

                context.update({
                    'driver_name': f"{driver.first_name} {driver.last_name}" if driver else "Assigned Driver",
                    'driver_phone': driver.phone if driver and hasattr(driver, "phone") else "",
                    'delivery_address': delivery_address if delivery_address else {"street_address": "", "city": ""},
                })

            # Choose template depending on status
            if new_status == "picked_up":
                html_template = "emails/order_picked_up.html"
            else:
                html_template = "emails/order_status_update.html"

            subject = f"Order #{order.order_number} Update - {new_status.replace('_', ' ').title()} - YumExpress"
            html_message = render_to_string(html_template, context)
            plain_message = render_to_string("emails/order_status_update.txt", context)

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.customer.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Order status update email sent to {order.customer.email} for order {order.order_number}")

        except Exception as e:
            logger.error(f"Failed to send order status update email: {str(e)}")
