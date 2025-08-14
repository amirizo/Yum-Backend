from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.admin.views.decorators import staff_member_required
import json
import logging
from .models import PaymentMethod, Payment, Refund, PayoutRequest, PaymentWebhookEvent
from .serializers import (
    PaymentMethodSerializer, PaymentCreateSerializer, PaymentConfirmSerializer,
    PaymentSerializer, RefundCreateSerializer, RefundSerializer,
    PayoutRequestSerializer, PayoutRequestCreateSerializer
)
from .services import ClickPesaService
from orders.models import Order
from authentication.services import SMSService

User = get_user_model()
logger = logging.getLogger(__name__)

class PaymentMethodListView(generics.ListAPIView):
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user, is_active=True)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_payment_intent(request):
    """Create payment intent for different payment methods"""
    serializer = PaymentCreateSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        order_id = serializer.validated_data['order_id']
        payment_type = serializer.validated_data.get('payment_type', 'card')
        phone_number = serializer.validated_data.get('mobile_number')
        
        try:
            order = Order.objects.get(id=order_id, customer=request.user)
            
            # Create Payment record
            payment = Payment.objects.create(
                order=order,
                user=request.user,
                amount=order.total_amount,
                currency='TZS',
                payment_type=payment_type,
                status='pending'
            )
            
            # Handle different payment types
            if payment_type == 'cash':
                # Cash on delivery - requires admin confirmation
                payment.status = 'pending_admin_approval'
                payment.save()
                
                send_admin_cash_order_notification(order, payment)
                
                return Response({
                    'payment_id': payment.id,
                    'status': 'pending_admin_approval',
                    'message': 'Cash on delivery order created. Waiting for admin approval.',
                    'payment_type': payment_type
                })
            
            elif payment_type in ['card', 'mobile_money']:
                # Process with ClickPesa
                clickpesa_service = ClickPesaService()
                
                clickpesa_response = clickpesa_service.create_payment_request(
                    amount=float(order.total_amount),
                    currency='TZS',
                    payment_type=payment_type,
                    phone_number=phone_number,
                    reference=f"ORDER-{order.id}",
                    description=f"Payment for order #{order.order_number}",
                    callback_url=f"{settings.SITE_URL}/api/payments/webhook/clickpesa/",
                    metadata={
                        'order_id': str(order.id),
                        'payment_id': str(payment.id),
                        'customer_id': str(request.user.id)
                    }
                )
                
                if clickpesa_response.get('success'):
                    payment.clickpesa_payment_id = clickpesa_response.get('payment_id')
                    payment.clickpesa_reference = clickpesa_response.get('reference')
                    payment.save()
                    
                    return Response({
                        'payment_id': payment.id,
                        'clickpesa_payment_id': clickpesa_response.get('payment_id'),
                        'payment_url': clickpesa_response.get('payment_url'),
                        'status': 'pending',
                        'payment_type': payment_type,
                        'message': 'Payment request created successfully'
                    })
                else:
                    payment.status = 'failed'
                    payment.failure_reason = clickpesa_response.get('message', 'Payment creation failed')
                    payment.save()
                    
                    return Response({
                        'error': clickpesa_response.get('message', 'Payment creation failed')
                    }, status=status.HTTP_400_BAD_REQUEST)
            
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment creation error: {str(e)}")
            return Response({'error': 'Payment creation failed'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def confirm_payment(request):
    """Confirm payment status"""
    serializer = PaymentConfirmSerializer(data=request.data)
    if serializer.is_valid():
        payment_id = serializer.validated_data.get('payment_id')
        clickpesa_payment_id = serializer.validated_data.get('clickpesa_payment_id')
        
        try:
            if payment_id:
                payment = Payment.objects.get(id=payment_id, user=request.user)
            else:
                payment = Payment.objects.get(clickpesa_payment_id=clickpesa_payment_id, user=request.user)
            
            if payment.payment_type in ['card', 'mobile_money'] and payment.clickpesa_payment_id:
                clickpesa_service = ClickPesaService()
                status_response = clickpesa_service.check_payment_status(payment.clickpesa_payment_id)
                
                if status_response.get('success'):
                    clickpesa_status = status_response.get('status')
                    payment.clickpesa_status = clickpesa_status
                    
                    if clickpesa_status in ['SUCCESS', 'SETTLED']:
                        payment.status = 'succeeded'
                        payment.processed_at = timezone.now()
                        
                        # Update order payment status
                        order = payment.order
                        order.payment_status = 'paid'
                        order.status = 'confirmed'
                        order.save()
                        
                        # Create order status history
                        from orders.models import OrderStatusHistory
                        OrderStatusHistory.objects.create(
                            order=order,
                            status='confirmed',
                            changed_by=request.user,
                            notes='Payment confirmed via ClickPesa'
                        )
                        
                        send_payment_success_notifications(payment, order, request.user)
                        
                    elif clickpesa_status in ['FAILED', 'CANCELLED']:
                        payment.status = 'failed'
                        payment.failure_reason = status_response.get('message', 'Payment failed')
                    
                    payment.save()
            
            return Response({
                'payment_id': payment.id,
                'status': payment.status,
                'clickpesa_status': payment.clickpesa_status,
                'payment_type': payment.payment_type
            })
            
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment confirmation error: {str(e)}")
            return Response({'error': 'Payment confirmation failed'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mobile_money_payment(request):
    """Initiate mobile money payment"""
    order_id = request.data.get('order_id')
    phone_number = request.data.get('phone_number')
    provider = request.data.get('provider', 'mpesa')  # mpesa, tigopesa, airtel
    
    if not all([order_id, phone_number]):
        return Response({'error': 'Order ID and phone number are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        order = Order.objects.get(id=order_id, customer=request.user)
        
        # Create payment record
        payment = Payment.objects.create(
            order=order,
            user=request.user,
            amount=order.total_amount,
            currency='TZS',
            payment_type='mobile_money',
            mobile_number=phone_number,
            mobile_money_provider=provider,
            status='pending'
        )
        
        clickpesa_service = ClickPesaService()
        response = clickpesa_service.initiate_mobile_money_payment(
            amount=float(order.total_amount),
            phone_number=phone_number,
            provider=provider,
            reference=f"ORDER-{order.id}",
            callback_url=f"{settings.SITE_URL}/api/payments/webhook/clickpesa/"
        )
        
        if response.get('success'):
            payment.clickpesa_payment_id = response.get('payment_id')
            payment.clickpesa_reference = response.get('reference')
            payment.save()
            
            return Response({
                'payment_id': payment.id,
                'status': 'pending',
                'message': f'Mobile money payment initiated. Please check your {provider} for payment prompt.',
                'reference': response.get('reference')
            })
        else:
            payment.status = 'failed'
            payment.failure_reason = response.get('message', 'Mobile money payment failed')
            payment.save()
            
            return Response({'error': response.get('message', 'Mobile money payment failed')}, 
                          status=status.HTTP_400_BAD_REQUEST)
            
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Mobile money payment error: {str(e)}")
        return Response({'error': 'Mobile money payment failed'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def confirm_cash_order(request):
    """Admin endpoint to confirm or reject cash on delivery orders"""
    order_id = request.data.get('order_id')
    action = request.data.get('action')  # 'approve' or 'reject'
    reason = request.data.get('reason', '')
    
    if not all([order_id, action]):
        return Response({'error': 'Order ID and action are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if action not in ['approve', 'reject']:
        return Response({'error': 'Action must be approve or reject'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        order = Order.objects.get(id=order_id)
        payment = Payment.objects.get(order=order, payment_type='cash', status='pending_admin_approval')
        
        if action == 'approve':
            payment.status = 'approved'
            payment.approved_by = request.user
            payment.approved_at = timezone.now()
            payment.save()
            
            # Update order status
            order.payment_status = 'approved'
            order.status = 'confirmed'
            order.save()
            
            # Create order status history
            from orders.models import OrderStatusHistory
            OrderStatusHistory.objects.create(
                order=order,
                status='confirmed',
                changed_by=request.user,
                notes='Cash on delivery order approved by admin'
            )
            
            # Send approval notification to customer
            send_cash_order_approved_notification(payment, order, order.customer)
            
            return Response({
                'message': 'Cash order approved successfully',
                'order_id': order.id,
                'status': 'approved'
            })
            
        else:  # reject
            payment.status = 'rejected'
            payment.rejection_reason = reason
            payment.rejected_by = request.user
            payment.rejected_at = timezone.now()
            payment.save()
            
            # Update order status
            order.payment_status = 'rejected'
            order.status = 'cancelled'
            order.save()
            
            # Create order status history
            from orders.models import OrderStatusHistory
            OrderStatusHistory.objects.create(
                order=order,
                status='cancelled',
                changed_by=request.user,
                notes=f'Cash on delivery order rejected by admin: {reason}'
            )
            
            # Send rejection notification to customer
            send_cash_order_rejected_notification(payment, order, order.customer, reason)
            
            return Response({
                'message': 'Cash order rejected successfully',
                'order_id': order.id,
                'status': 'rejected'
            })
            
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    except Payment.DoesNotExist:
        return Response({'error': 'Payment not found or not pending approval'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Cash order confirmation error: {str(e)}")
        return Response({'error': 'Cash order confirmation failed'}, status=status.HTTP_400_BAD_REQUEST)


def send_payment_success_notifications(payment, order, user):
    """Send SMS and email notifications after successful payment"""
    try:
        # Send SMS notification
        sms_service = SMSService()
        sms_message = f"Thank you for your order with YumExpress! Your payment of TZS {payment.amount:,.0f} has been confirmed. Order #{order.order_number} is now being prepared. Track: {settings.SITE_URL}/orders/{order.id}"
        sms_service.send_sms(user.phone_number, sms_message)
        
        # Send email notification
        context = {
            'user': user,
            'order': order,
            'payment': payment,
            'site_url': settings.SITE_URL
        }
        
        html_message = render_to_string('emails/payment_success.html', context)
        plain_message = render_to_string('emails/payment_success.txt', context)
        
        send_mail(
            subject=f'Payment Confirmed - Order #{order.order_number}',
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f"Payment success notifications sent for order {order.id}")
        
    except Exception as e:
        logger.error(f"Error sending payment success notifications: {str(e)}")

def send_admin_cash_order_notification(order, payment):
    """Send notification to admin about new cash order"""
    try:
        context = {
            'order': order,
            'payment': payment,
            'customer': order.customer,
            'site_url': settings.SITE_URL
        }
        
        html_message = render_to_string('emails/admin_cash_order_confirmation.html', context)
        
        # Send to all admin users
        admin_emails = User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True)
        
        send_mail(
            subject=f'Cash Order Needs Confirmation - #{order.order_number}',
            message=f'A new cash on delivery order #{order.order_number} needs admin confirmation.',
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(admin_emails),
            fail_silently=False,
        )
        
        logger.info(f"Admin cash order notification sent for order {order.id}")
        
    except Exception as e:
        logger.error(f"Error sending admin cash order notification: {str(e)}")

def send_cash_order_approved_notification(payment, order, user):
    """Send notification when cash order is approved"""
    try:
        # Send SMS notification
        sms_service = SMSService()
        sms_message = f"Great news! Your cash on delivery order #{order.order_number} has been approved. Total: TZS {payment.amount:,.0f}. Please have exact amount ready for delivery."
        sms_service.send_sms(user.phone_number, sms_message)
        
        # Send email notification
        context = {
            'user': user,
            'order': order,
            'payment': payment,
            'site_url': settings.SITE_URL
        }
        
        html_message = render_to_string('emails/cash_order_approved.html', context)
        
        send_mail(
            subject=f'Order Approved - #{order.order_number}',
            message=f'Your cash on delivery order #{order.order_number} has been approved.',
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f"Cash order approval notification sent for order {order.id}")
        
    except Exception as e:
        logger.error(f"Error sending cash order approval notification: {str(e)}")

def send_cash_order_rejected_notification(payment, order, user, reason):
    """Send notification when cash order is rejected"""
    try:
        # Send SMS notification
        sms_service = SMSService()
        sms_message = f"Sorry, your cash on delivery order #{order.order_number} could not be approved. Reason: {reason}. Please try again or contact support."
        sms_service.send_sms(user.phone_number, sms_message)
        
        # Send email notification
        context = {
            'user': user,
            'order': order,
            'payment': payment,
            'reason': reason,
            'site_url': settings.SITE_URL
        }
        
        html_message = render_to_string('emails/cash_order_rejected.html', context)
        
        send_mail(
            subject=f'Order Update - #{order.order_number}',
            message=f'Your cash on delivery order #{order.order_number} could not be approved.',
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f"Cash order rejection notification sent for order {order.id}")
        
    except Exception as e:
        logger.error(f"Error sending cash order rejection notification: {str(e)}")

class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).order_by('-created_at')

class PaymentDetailView(generics.RetrieveAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

class RefundCreateView(generics.CreateAPIView):
    serializer_class = RefundCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        payment = serializer.validated_data['payment']
        amount = serializer.validated_data['amount']
        reason = serializer.validated_data['reason']
        
        try:
            if payment.clickpesa_payment_id:
                clickpesa_service = ClickPesaService()
                refund_response = clickpesa_service.create_refund(
                    payment_id=payment.clickpesa_payment_id,
                    amount=float(amount),
                    reason=reason
                )
                
                if refund_response.get('success'):
                    refund = serializer.save(
                        clickpesa_refund_id=refund_response.get('refund_id'),
                        status='pending'
                    )
                    return refund
                else:
                    raise serializers.ValidationError(f"Refund failed: {refund_response.get('message')}")
            else:
                # For cash payments, create manual refund
                refund = serializer.save(status='manual_review')
                return refund
                
        except Exception as e:
            logger.error(f"Refund creation error: {str(e)}")
            raise serializers.ValidationError(f"Refund failed: {str(e)}")

class RefundListView(generics.ListAPIView):
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Refund.objects.filter(payment__user=self.request.user).order_by('-created_at')

class PayoutRequestListView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PayoutRequestCreateSerializer
        return PayoutRequestSerializer

    def get_queryset(self):
        if self.request.user.user_type == 'vendor':
            return PayoutRequest.objects.filter(vendor=self.request.user).order_by('-created_at')
        return PayoutRequest.objects.none()

    def perform_create(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise serializers.ValidationError("Only vendors can request payouts")
        serializer.save(vendor=self.request.user)


@method_decorator(csrf_exempt, name='dispatch')
@api_view(['POST'])
@permission_classes([])
def clickpesa_webhook(request):
    """Handle ClickPesa webhook notifications"""
    try:
        payload = json.loads(request.body)
        
        event_type = payload.get('event_type')
        payment_data = payload.get('data', {})
        payment_id = payment_data.get('payment_id')
        
        # Store webhook event
        webhook_event, created = PaymentWebhookEvent.objects.get_or_create(
            clickpesa_event_id=payload.get('event_id', payment_id),
            defaults={
                'event_type': event_type,
                'data': payload,
            }
        )
        
        if created:
            # Process the event
            if event_type == 'payment.completed':
                handle_payment_succeeded(payment_data)
            elif event_type == 'payment.failed':
                handle_payment_failed(payment_data)
            elif event_type == 'refund.completed':
                handle_refund_completed(payment_data)
            
            webhook_event.processed = True
            webhook_event.save()
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"ClickPesa webhook error: {str(e)}")
        return HttpResponse(status=400)

def handle_payment_succeeded(payment_data):
    """Handle successful payment webhook"""
    try:
        payment_id = payment_data.get('payment_id')
        payment = Payment.objects.get(clickpesa_payment_id=payment_id)
        
        payment.status = 'succeeded'
        payment.clickpesa_status = 'completed'
        payment.processed_at = timezone.now()
        payment.save()
        
        # Update order
        order = payment.order
        order.payment_status = 'paid'
        if order.status == 'pending':
            order.status = 'confirmed'
        order.save()
        
        # Create order status history
        from orders.models import OrderStatusHistory
        OrderStatusHistory.objects.create(
            order=order,
            status='confirmed',
            notes='Payment confirmed via ClickPesa webhook'
        )
        
        send_payment_success_notifications(payment, order, payment.user)
        
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for ClickPesa ID: {payment_data.get('payment_id')}")

def handle_payment_failed(payment_data):
    """Handle failed payment webhook"""
    try:
        payment_id = payment_data.get('payment_id')
        payment = Payment.objects.get(clickpesa_payment_id=payment_id)
        
        payment.status = 'failed'
        payment.clickpesa_status = 'failed'
        payment.failure_reason = payment_data.get('failure_reason', 'Payment failed')
        payment.save()
        
        # Update order
        order = payment.order
        order.payment_status = 'failed'
        order.save()
        
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for ClickPesa ID: {payment_data.get('payment_id')}")

def handle_refund_completed(refund_data):
    """Handle completed refund webhook"""
    try:
        refund_id = refund_data.get('refund_id')
        refund = Refund.objects.get(clickpesa_refund_id=refund_id)
        
        refund.status = 'completed'
        refund.processed_at = timezone.now()
        refund.save()
        
        # Update payment status
        payment = refund.payment
        total_refunded = sum(r.amount for r in payment.refunds.filter(status='completed'))
        if total_refunded >= payment.amount:
            payment.status = 'refunded'
        else:
            payment.status = 'partially_refunded'
        payment.save()
        
    except Refund.DoesNotExist:
        logger.error(f"Refund not found for ClickPesa ID: {refund_data.get('refund_id')}")

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def payment_dashboard(request):
    """Payment dashboard with statistics"""
    if request.user.user_type == 'vendor':
        # Vendor payment dashboard
        from django.db.models import Sum, Count
        payments = Payment.objects.filter(order__vendor=request.user, status='succeeded')
        
        total_earnings = payments.aggregate(total=Sum('amount'))['total'] or 0
        payment_stats = payments.values('payment_type').annotate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        pending_payouts = PayoutRequest.objects.filter(
            vendor=request.user, 
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return Response({
            'total_earnings': total_earnings,
            'pending_payouts': pending_payouts,
            'payment_stats': payment_stats,
            'recent_payments': PaymentSerializer(payments[:10], many=True).data
        })
    else:
        # Customer payment dashboard
        payments = Payment.objects.filter(user=request.user)
        payment_stats = payments.values('payment_type', 'status').annotate(count=Count('id'))
        
        return Response({
            'total_payments': payments.count(),
            'successful_payments': payments.filter(status='succeeded').count(),
            'payment_stats': payment_stats,
            'recent_payments': PaymentSerializer(payments[:10], many=True).data
        })
