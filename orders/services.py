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
            subject = f"Order #{order.order_number} Confirmed - YumExpress"
            
            context = {
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'order_number': order.order_number,
                'vendor_name': f"{order.vendor.first_name} {order.vendor.last_name}",
                'estimated_time': order.estimated_delivery_time,
                'total_amount': order.total_amount,
                'order_items': order.items.all(),
                'delivery_address': order.delivery_address,
            }
            
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
            subject = f"Order #{order.order_number} Picked Up - YumExpress"
            
            context = {
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'order_number': order.order_number,
                'driver_name': f"{order.driver.first_name} {order.driver.last_name}" if order.driver else "Driver",
                'driver_phone': order.driver.phone_number if order.driver else "",
                'estimated_delivery': order.estimated_delivery_time,
                'delivery_address': order.delivery_address,
            }
            
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
            subject = f"Order #{order.order_number} Update - YumExpress"
            
            context = {
                'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
                'order_number': order.order_number,
                'vendor_name': f"{order.vendor.first_name} {order.vendor.last_name}",
                'rejection_reason': rejection_reason,
                'refund_amount': order.total_amount,
                'refund_timeline': "1 business days",
            }
            
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
