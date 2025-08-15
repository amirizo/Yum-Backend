from rest_framework import generics, permissions, status
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.utils import timezone
import json
import logging
from .models import PaymentMethod, Payment, Refund, PayoutRequest, PaymentWebhookEvent
from .serializers import (
    PaymentMethodSerializer, PaymentIntentCreateSerializer, PaymentConfirmSerializer,
    PaymentSerializer, RefundCreateSerializer, RefundSerializer,
    PayoutRequestSerializer, PayoutRequestCreateSerializer
)
from .services import ClickPesaService
from orders.models import Order
from authentication.services import SMSService, EmailService
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
    serializer = PaymentIntentCreateSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        order_id = serializer.validated_data['order_id']
        payment_type = serializer.validated_data.get('payment_type', 'card')
        
        try:
            order = Order.objects.get(id=order_id, customer=request.user)
            
            existing_payment = Payment.objects.filter(order=order).first()
            if existing_payment:
                if existing_payment.status in ['succeeded', 'processing']:
                    return Response({
                        'error': 'Payment already exists for this order',
                        'payment_id': existing_payment.id,
                        'status': existing_payment.status
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Delete failed/canceled payment to create new one
                    existing_payment.delete()
            
            clickpesa_service = ClickPesaService()
            
            if payment_type == 'cash':
                # Cash on delivery - create payment record but don't process
                payment = Payment.objects.create(
                    order=order,
                    user=request.user,
                    amount=order.total_amount,
                    currency='TZS',
                    payment_type='cash',
                    status='pending_admin_approval',
                    clickpesa_order_reference=f"CASH_{order.order_number}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
                )
                
                # Send notification to admin for cash order approval
                EmailService.send_admin_cash_order_notification(order, payment)
                
                return Response({
                    'payment_id': payment.id,
                    'status': 'pending_admin_approval',
                    'message': 'Cash on delivery order created. Waiting for admin approval.',
                    'payment_type': 'cash'
                })
                
            elif payment_type == 'mobile_money':
                # Mobile money payment
                phone_number = serializer.validated_data.get('phone_number')
                provider = serializer.validated_data.get('provider', 'mix_by_yas')
                
                if not phone_number:
                    return Response({'error': 'Phone number required for mobile money'}, 
                                  status=status.HTTP_400_BAD_REQUEST)
                
                # Create payment record first
                payment = Payment.objects.create(
                    order=order,
                    user=request.user,
                    amount=order.total_amount,
                    currency='TZS',
                    payment_type='mobile_money',
                    status='pending',
                    mobile_number=phone_number,
                    mobile_provider=provider
                )
                
                # Initiate mobile money payment with ClickPesa
                result = clickpesa_service.create_mobile_money_payment(
                    amount=float(order.total_amount),
                    phone_number=phone_number,
                    provider=provider,
                    order_reference=payment.clickpesa_order_reference,
                    # customer_name=f"{request.user.first_name} {request.user.last_name}",
                    # customer_email=request.user.email
                )



                
                if result['success']:
                    payment.clickpesa_payment_reference = result.get('payment_reference')
                    payment.save()
                    
                    return Response({
                        'payment_id': payment.id,
                        'status': 'pending',
                        'message': 'USSD push sent to your phone. Please complete payment.',
                        'payment_type': 'mobile_money',
                        'ussd_code': result.get('ussd_code')
                    })
                else:
                    payment.status = 'failed'
                    payment.failure_reason = result.get('error', 'Mobile money payment failed')
                    payment.save()
                    return Response({'error': result.get('error', 'Mobile money payment failed')}, 
                                  status=status.HTTP_400_BAD_REQUEST)
                    
            else:  # Card payment
                # Create payment record first
                payment = Payment.objects.create(
                    order=order,
                    user=request.user,
                    amount=order.total_amount,
                    currency='USD',  # ClickPesa uses USD for card payments
                    payment_type='card',
                    status='pending'
                )
                
                # Create card payment with ClickPesa
                result = clickpesa_service.create_card_payment(
                    amount=float(order.total_amount),
                    order_reference=payment.clickpesa_order_reference,
                    customer_name=f"{request.user.first_name} {request.user.last_name}",
                    customer_email=request.user.email,
                    customer_phone=request.user.phone_number  #
                )
                
                if result['success']:
                    payment.clickpesa_payment_reference = result.get('payment_reference')
                    payment.payment_link = result.get('payment_link')
                    payment.save()
                    
                    return Response({
                        'payment_id': payment.id,
                        'payment_link': result.get('payment_link'),
                        'status': 'pending',
                        'message': 'Please complete payment using the provided link.',
                        'payment_type': 'card'
                    })
                else:
                    payment.status = 'failed'
                    payment.failure_reason = result.get('error', 'Card payment failed')
                    payment.save()
                    return Response({'error': result.get('error', 'Card payment failed')}, 
                                  status=status.HTTP_400_BAD_REQUEST)
            
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment creation error: {str(e)}")
            return Response({'error': 'Payment creation failed'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def confirm_payment(request):
    serializer = PaymentConfirmSerializer(data=request.data)
    if serializer.is_valid():
        payment_id = serializer.validated_data['payment_id']
        
        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
            
            clickpesa_service = ClickPesaService()
            result = clickpesa_service.check_payment_status(payment.clickpesa_order_reference)
            
            if result['success']:
                payment_data = result['data']
                old_status = payment.status

                
                if isinstance(payment_data, list) and len(payment_data) > 0:
                    payment_data = payment_data[0]
                
                # Update payment status based on ClickPesa response
                if payment_data['status'] in ['SUCCESS', 'SETTLED']:
                    payment.status = 'succeeded'
                    payment.processed_at = timezone.now()
                    payment.clickpesa_payment_reference = payment_data.get('paymentReference')
                    
                    # Update order status
                    order = payment.order
                    order.payment_status = 'paid'
                    order.status = 'confirmed'
                    order.save()
                    
                    if old_status != 'succeeded':
                        # Send SMS
                        SMSService.send_payment_success_sms(
                            phone_number=request.user.phone_number,
                            order_number=order.order_number,
                            amount=payment.amount
                        )
                        
                        # Send Email
                        EmailService.send_payment_success_email(
                            user=request.user,
                            order=order,
                            payment=payment
                        )
                    
                elif payment_data['status'] == 'FAILED':
                    payment.status = 'failed'
                    payment.failure_reason = 'Payment failed at gateway'
                elif payment_data['status'] in ['PROCESSING', 'PENDING']:
                    payment.status = 'processing'
                
                payment.save()
                
                return Response({
                    'status': payment.status,
                    'payment_status': payment.status,
                    'message': 'Payment status updated successfully'
                })
            else:
                return Response({'error': 'Failed to check payment status'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment confirmation error: {str(e)}")
            return Response({'error': 'Payment confirmation failed'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def approve_cash_order(request):
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    payment_id = request.data.get('payment_id')
    action = request.data.get('action')  # 'approve' or 'reject'
    
    try:
        payment = Payment.objects.get(id=payment_id, payment_type='cash', status='pending_admin_approval')
        order = payment.order
        
        if action == 'approve':
            payment.status = 'succeeded'
            payment.processed_at = timezone.now()
            order.payment_status = 'paid'
            order.status = 'confirmed'
            order.save()
            payment.save()
            
            # Send approval notification
            EmailService.send_cash_order_approved_email(payment.user, order, payment)
            SMSService.send_sms(
                phone_number=payment.user.phone_number,
                message=f"Your cash order #{order.order_number} has been approved and is being processed."
            )
            
            return Response({'message': 'Cash order approved successfully'})
            
        elif action == 'reject':
            payment.status = 'failed'
            payment.failure_reason = 'Rejected by admin'
            order.payment_status = 'failed'
            order.status = 'cancelled'
            order.save()
            payment.save()
            
            # Send rejection notification
            EmailService.send_cash_order_rejected_email(payment.user, order, payment)
            SMSService.send_sms(
                phone_number=payment.user.phone_number,
                message=f"Your cash order #{order.order_number} has been rejected. Please contact support."
            )
            
            return Response({'message': 'Cash order rejected'})
        else:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
            
    except Payment.DoesNotExist:
        return Response({'error': 'Cash payment not found'}, status=status.HTTP_404_NOT_FOUND)

class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

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
            clickpesa_service = ClickPesaService()
            result = clickpesa_service.process_refund(
                payment_reference=payment.clickpesa_payment_reference,
                amount=float(amount),
                reason=reason
            )
            
            if result['success']:
                refund = serializer.save(
                    clickpesa_refund_id=result.get('refund_id'),
                    status='pending'
                )
                return refund
            else:
                raise serializers.ValidationError(f"Refund failed: {result.get('error')}")
            
        except Exception as e:
            logger.error(f"Refund creation error: {str(e)}")
            raise serializers.ValidationError(f"Refund failed: {str(e)}")

class RefundListView(generics.ListAPIView):
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Refund.objects.filter(payment__user=self.request.user)

class PayoutRequestListView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PayoutRequestCreateSerializer
        return PayoutRequestSerializer

    def get_queryset(self):
        if self.request.user.user_type == 'vendor':
            return PayoutRequest.objects.filter(vendor=self.request.user)
        return PayoutRequest.objects.none()

    def perform_create(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise serializers.ValidationError("Only vendors can request payouts")
        serializer.save(vendor=self.request.user)



@csrf_exempt
@api_view(['POST'])
@permission_classes([])
def clickpesa_webhook(request):
    """Handle ClickPesa webhook events"""
    try:
        payload = json.loads(request.body)
        payment_data = payload.get('data', {})

        event_type = payload.get('event_type') or payload.get('event')
        if not event_type:
            logger.error("Invalid webhook payload (no event): %s", payload)
            return HttpResponse(status=400)
        
        # Store webhook event
        webhook_event, created = PaymentWebhookEvent.objects.get_or_create(
            clickpesa_event_id=payment_data.get('paymentReference', ''),
            defaults={
                'event_type': event_type,
                'data': payload,
            }
        )

        if created:
            # Process the event
            if event_type == 'payment.success':
                handle_payment_succeeded(payment_data)
            elif event_type == 'payment.failed':
                handle_payment_failed(payment_data)
            elif event_type == 'refund.processed':
                handle_refund_processed(payment_data)
            
            webhook_event.processed = True
            webhook_event.save()

        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return HttpResponse(status=400)

def handle_payment_succeeded(payment_data):
    try:
        order_reference = payment_data.get('orderReference')
        payment = Payment.objects.get(clickpesa_order_reference=order_reference)
        
        if payment.status != 'succeeded':
            payment.status = 'succeeded'
            payment.processed_at = timezone.now()
            payment.clickpesa_payment_reference = payment_data.get('paymentReference')
            payment.save()
            
            # Update order
            order = payment.order
            order.payment_status = 'paid'
            if order.status == 'pending':
                order.status = 'confirmed'
            order.save()
            
            SMSService.send_payment_success_sms(
                phone_number=payment.user.phone_number,
                order_number=order.order_number,
                amount=payment.amount
            )
            
            EmailService.send_payment_success_email(
                user=payment.user,
                order=order,
                payment=payment
            )
        
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for order reference: {payment_data.get('orderReference')}")

def handle_payment_failed(payment_data):
    try:
        order_reference = payment_data.get('orderReference')
        payment = Payment.objects.get(clickpesa_order_reference=order_reference)
        payment.status = 'failed'
        payment.failure_reason = payment_data.get('failureReason', 'Payment failed')
        payment.save()
        
        # Update order
        order = payment.order
        order.payment_status = 'failed'
        order.save()
        
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for order reference: {payment_data.get('orderReference')}")

def handle_refund_processed(refund_data):
    try:
        refund_id = refund_data.get('refundId')
        refund = Refund.objects.get(clickpesa_refund_id=refund_id)
        refund.status = refund_data.get('status', 'succeeded')
        if refund.status == 'succeeded':
            refund.processed_at = timezone.now()
        refund.save()
        
        # Update payment status
        payment = refund.payment
        total_refunded = sum(r.amount for r in payment.refunds.filter(status='succeeded'))
        if total_refunded >= payment.amount:
            payment.status = 'refunded'
        else:
            payment.status = 'partially_refunded'
        payment.save()
        
    except Refund.DoesNotExist:
        logger.error(f"Refund not found for ID: {refund_data.get('refundId')}")

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def payment_dashboard(request):
    if request.user.user_type == 'vendor':
        # Vendor payment dashboard
        from django.db.models import Sum
        payments = Payment.objects.filter(order__vendor=request.user, status='succeeded')
        total_earnings = payments.aggregate(total=Sum('amount'))['total'] or 0
        pending_payouts = PayoutRequest.objects.filter(vendor=request.user, status='pending').aggregate(total=Sum('amount'))['total'] or 0
        
        return Response({
            'total_earnings': total_earnings,
            'pending_payouts': pending_payouts,
            'recent_payments': PaymentSerializer(payments[:10], many=True).data
        })
    else:
        # Customer payment dashboard
        payments = Payment.objects.filter(user=request.user)
        return Response({
            'total_payments': payments.count(),
            'successful_payments': payments.filter(status='succeeded').count(),
            'recent_payments': PaymentSerializer(payments[:10], many=True).data
        })
