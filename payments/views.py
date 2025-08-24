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
from decimal import Decimal
from geopy.distance import geodesic
from datetime import timedelta
import json
import logging
from django.db import transaction
from .models import PaymentMethod, Payment, Refund, PayoutRequest, PaymentWebhookEvent
from .serializers import (
    PaymentMethodSerializer, PaymentIntentCreateSerializer, PaymentConfirmSerializer,
    PaymentSerializer, RefundCreateSerializer, RefundSerializer,
    PayoutRequestSerializer, PayoutRequestCreateSerializer
)
from .services import ClickPesaService
from orders.models import Order, DeliveryAddress
from orders.utils import restore_cart_for_user
from authentication.services import SMSService, EmailService
from orders.serializers import OrderSerializer
User = get_user_model()
logger = logging.getLogger(__name__)

class PaymentMethodListView(generics.ListAPIView):
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Return active payment methods for the authenticated user
        return PaymentMethod.objects.filter(user=self.request.user, is_active=True)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_order_and_payment(request):
    """Compatibility wrapper: delegates to the main checkout endpoint implementation.
    Keeps a single source of truth for checkout logic in `checkout`.
    """
    try:
        # Delegate to checkout view which already implements full atomic flow
        return checkout(request)
    except Exception as e:
        logger.error('create_order_and_payment wrapper error: %s', e)
        return Response({'error': 'Order creation failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    """Handle ClickPesa webhook events.

    This endpoint accepts ClickPesa webhook payloads that may use different
    key names for the event and ids. It will:
    - normalize event names (PAYMENT RECEIVED, PAYMENT FAILED, REFUND ...)
    - extract payment/order identifiers from multiple possible keys
    - deduplicate events using `PaymentWebhookEvent.clickpesa_event_id`
    - dispatch to the internal handlers below
    """
    try:
        payload = json.loads(request.body)

        # Normalize event name from common variants providers use
        raw_event = (
            payload.get('event')
            or payload.get('eventType')
            or payload.get('event_type')
            or payload.get('type')
            or ''
        )
        raw_event_str = str(raw_event).upper()

        # Map provider event strings to our internal event keys
        if 'PAYMENT RECEIVED' in raw_event_str or raw_event_str in ('PAYMENT_RECEIVED', 'PAYMENT.RECEIVED', 'PAYMENTRECEIVED'):
            event = 'payment.received'
        elif 'PAYMENT FAILED' in raw_event_str or raw_event_str in ('PAYMENT_FAILED', 'PAYMENT.FAILED', 'PAYMENTFAILED'):
            event = 'payment.failed'
        elif 'REFUND' in raw_event_str or 'REFUND.PROCESSED' in raw_event_str:
            event = 'refund.processed'
        else:
            # Fallback: use lowercased raw string so unknown events are still recorded
            event = raw_event_str.lower() if raw_event_str else 'unknown'

        # Extract the data block - ClickPesa may nest payload under 'data' or provide top-level fields
        payment_data = payload.get('data') if isinstance(payload.get('data'), dict) else payload.get('data') or payload
        if payment_data is None:
            payment_data = {}

        # Determine a deduplication id from common provider keys
        clickpesa_event_id = (
            payment_data.get('paymentReference')
            or payment_data.get('paymentId')
            or payment_data.get('id')
            or payload.get('id')
            or ''
        )

        # Store the raw webhook for auditing and ensure we don't process duplicates
        webhook_event, created = PaymentWebhookEvent.objects.get_or_create(
            clickpesa_event_id=clickpesa_event_id,
            defaults={
                'event_type': event,
                'data': payload,
            }
        )

        if created:
            # Dispatch to handlers
            if event == 'payment.received':
                handle_payment_succeeded(payment_data)
            elif event == 'payment.failed':
                handle_payment_failed(payment_data)
            elif event == 'refund.processed':
                handle_refund_processed(payment_data)
            else:
                logger.info('Unhandled ClickPesa webhook event: %s; payload id=%s', raw_event_str, clickpesa_event_id)

            webhook_event.processed = True
            webhook_event.save()

        return HttpResponse(status=200)

    except Exception as e:
        # Log the body to help debug malformed payloads
        body_preview = ''
        try:
            body_preview = request.body.decode('utf-8')[:2000]
        except Exception:
            body_preview = str(request.body)[:2000]

        logger.error('Webhook processing error: %s - body=%s', str(e), body_preview)
        return HttpResponse(status=400)



def handle_payment_succeeded(payment_data):
    """Handle successful payment webhook from ClickPesa.

    This function is resilient to different key names in provider payloads and
    will try to locate the related Payment by order reference or payment reference.
    """
    try:
        # Accept multiple possible key names
        order_reference = (
            payment_data.get('orderReference')
            or payment_data.get('order_reference')
            or payment_data.get('orderId')
            or payment_data.get('order_id')
        )
        payment_reference = (
            payment_data.get('paymentReference')
            or payment_data.get('paymentId')
            or payment_data.get('id')
        )

        # Find payment either by order reference or by provider payment reference
        payment = None
        if order_reference:
            payment = Payment.objects.filter(clickpesa_order_reference=order_reference).first()
        if not payment and payment_reference:
            payment = Payment.objects.filter(clickpesa_payment_reference=payment_reference).first()

        if not payment:
            logger.error('Payment not found for webhook (success). order_reference=%s payment_reference=%s data=%s',
                         order_reference, payment_reference, payment_data)
            return

        # Normalize status field variants
        status_str = (payment_data.get('status') or payment_data.get('paymentStatus') or '').upper()

        if status_str in ['SUCCESS', 'SETTLED', 'COMPLETED', 'SUCCEEDED', 'OK', 'PAID']:
            if payment.status != 'succeeded':
                payment.status = 'succeeded'
                payment.processed_at = timezone.now()
                if payment_reference:
                    payment.clickpesa_payment_reference = payment_reference
                payment.save()

                # Update order payment status only; do NOT auto-confirm the order.
                order = payment.order
                order.payment_status = 'paid'
                # Keep order.status unchanged so vendor confirms order manually
                order.save()

                # Update product stock and notify parties
                for item in order.items.all():
                    product = item.product
                    if product.stock_quantity >= item.quantity:
                        product.stock_quantity -= item.quantity
                        product.save()

                try:
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

                    from orders.services import OrderNotificationService
                    OrderNotificationService.send_new_order_notification(order)

                    # Notify frontend via WebSocket and other channels
                    try:
                        from notifications.services import NotificationService
                        NotificationService.send_order_status_notification(order, old_status=None)
                    except Exception as e:
                        logger.warning('Failed to broadcast payment success notification for order %s: %s', order.order_number, e)

                except Exception as e:
                    logger.warning('Failed to send notifications for payment %s: %s', payment.id, e)
        else:
            logger.info('Payment webhook received non-success status: %s for payment id=%s', status_str, payment.id if payment else None)

    except Payment.DoesNotExist:
        logger.error('Payment not found for order reference: %s', payment_data.get('orderReference') or payment_data.get('order_reference'))
    except Exception as e:
        logger.error('Error handling payment success: %s - data=%s', e, payment_data)



def handle_payment_failed(payment_data):
    """Handle failed payment webhook from ClickPesa."""
    try:
        order_reference = (
            payment_data.get('orderReference')
            or payment_data.get('order_reference')
            or payment_data.get('orderId')
            or payment_data.get('order_id')
        )
        payment_reference = (
            payment_data.get('paymentReference')
            or payment_data.get('paymentId')
            or payment_data.get('id')
        )

        payment = None
        if order_reference:
            payment = Payment.objects.filter(clickpesa_order_reference=order_reference).first()
        if not payment and payment_reference:
            payment = Payment.objects.filter(clickpesa_payment_reference=payment_reference).first()

        if not payment:
            logger.error('Payment not found for webhook (failed). order_reference=%s payment_reference=%s data=%s',
                         order_reference, payment_reference, payment_data)
            return

        # Extract human readable failure reason if available
        failure_reason = (
            payment_data.get('message')
            or payment_data.get('failureReason')
            or payment_data.get('reason')
            or str(payment_data.get('status'))
        )

        payment.status = 'failed'
        payment.failure_reason = failure_reason
        payment.save()

        # Attempt to restore the user's cart from snapshot when payment failed
        try:
            if getattr(payment, 'cart_snapshot', None) and payment.payment_type in ('mobile_money', 'card'):
                restored = restore_cart_for_user(payment.user, payment.cart_snapshot)
                if restored:
                    logger.info('Restored cart for user %s from failed payment %s snapshot', payment.user.id, payment.id)
                    # Clear the snapshot to avoid duplicate restores
                    payment.cart_snapshot = None
                    payment.save()
                else:
                    logger.warning('Failed to restore cart for user %s from failed payment %s snapshot', payment.user.id, payment.id)
        except Exception as e:
            logger.exception('Error restoring cart for failed payment %s: %s', getattr(payment, 'id', None), e)

        # Update order
        order = payment.order
        order.payment_status = 'failed'
        order.status = 'cancelled'
        order.save()

        # Send failure notification (best-effort)
        try:
            SMSService.send_sms(
                phone_number=payment.user.phone_number,
                message=f"Payment failed for order #{order.order_number}. Reason: {failure_reason}"
            )
        except Exception as e:
            logger.warning('Failed to send failure notification: %s', e)

        # Broadcast failure to frontend and create notifications
        try:
            from notifications.services import NotificationService
            NotificationService.send_order_status_notification(order, old_status=None)
        except Exception as e:
            logger.warning('Failed to broadcast payment failure notification for order %s: %s', order.order_number, e)

    except Payment.DoesNotExist:
        logger.error('Payment not found for order reference: %s', payment_data.get('orderReference'))
    except Exception as e:
        logger.error('Error handling payment failure: %s - data=%s', e, payment_data)



def handle_refund_processed(refund_data):
    try:
        refund_id = refund_data.get('refundId') or refund_data.get('id')
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
        logger.error('Refund not found for ID: %s', refund_data.get('refundId'))



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



        

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def checkout(request):
    """Atomic checkout endpoint: validates input, creates Order+Payment inside a transaction,
    initiates external payment (mobile_money/card) or marks cash as pending, and returns unified JSON.
    Map this view to POST /api/checkout/ in your URLs.
    """
    from orders.models import Order, OrderItem, Cart
    from orders.utils import clear_cart
    from authentication.models import Vendor
    from orders.checkout_serializers import CheckoutValidationSerializer
    from orders.models import calculate_delivery_fee

    try:
        serializer = CheckoutValidationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        vendor = Vendor.objects.get(id=data['vendor_id'], status='active')
        vendor_location = vendor.primary_location

        # Get user's cart for this vendor
        cart = Cart.objects.filter(user=request.user, vendor=vendor).first()
        if not cart or not cart.items.exists():
            return Response({'error': 'Cart is empty for this vendor'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate delivery fee and totals
        delivery_address_data = data['delivery_address']
        delivery_fee = Decimal(str(calculate_delivery_fee(
            float(delivery_address_data['latitude']),
            float(delivery_address_data['longitude']),
            float(vendor_location.latitude),
            float(vendor_location.longitude)
        )))

        cart_total = cart.total_amount
        tax_rate = Decimal('0.00')
        tax_amount = (cart_total * tax_rate).quantize(Decimal("0.01"))
        grand_total = (cart_total + delivery_fee + tax_amount).quantize(Decimal("0.01"))

        payment_method_data = data['payment_method']
        payment_type = payment_method_data['payment_type']
        phone_number = payment_method_data.get('phone_number')
        provider = payment_method_data.get('provider', 'mix_by_yas')

        clickpesa_service = ClickPesaService()

        # All DB changes should be atomic and rolled back if external payment initiation fails
        with transaction.atomic():
            # Create order
            order = Order.objects.create(
                customer=request.user,
                vendor=vendor,
                delivery_address_text=delivery_address_data.get('address', ''),
                delivery_latitude=delivery_address_data['latitude'],
                delivery_longitude=delivery_address_data['longitude'],
                subtotal=cart_total,
                delivery_fee=delivery_fee,
                tax_amount=tax_amount,
                total_amount=grand_total,
                special_instructions=data.get('special_instructions', ''),
                status='pending',
                payment_status='pending'
            )

            # If client requested to save the delivery address, persist it for the user
            try:
                save_address = bool(data.get('save_address'))
                address_label = data.get('address_label') or delivery_address_data.get('label') or 'Delivery'
                if save_address and request.user and request.user.is_authenticated:
                    # Build DeliveryAddress fields from payload
                    da = {
                        'user': request.user,
                        'label': address_label,
                        'street_address': delivery_address_data.get('street_name') or delivery_address_data.get('address', ''),
                        'city': delivery_address_data.get('city', ''),
                        'state': delivery_address_data.get('state', ''),
                        'country': delivery_address_data.get('country', 'Tanzania'),
                        'latitude': delivery_address_data.get('latitude'),
                        'longitude': delivery_address_data.get('longitude'),
                        'place_id': (delivery_address_data.get('place_id') or '')[:255],
                        'formatted_address': (delivery_address_data.get('formatted_address') or '')[:255],
                        'phone': delivery_address_data.get('phone') or getattr(request.user, 'phone_number', '')
                    }

                    try:
                        # Try to find an existing address by place_id or lat/lon
                        delivery_address_obj = None
                        if da['place_id']:
                            delivery_address_obj = DeliveryAddress.objects.filter(user=request.user, place_id=da['place_id']).first()
                        if not delivery_address_obj and da['latitude'] and da['longitude']:
                            delivery_address_obj = DeliveryAddress.objects.filter(user=request.user, latitude=da['latitude'], longitude=da['longitude']).first()

                        if delivery_address_obj:
                            # update fields
                            for k, v in da.items():
                                if k == 'user':
                                    continue
                                setattr(delivery_address_obj, k, v)
                            delivery_address_obj.save()
                        else:
                            delivery_address_obj = DeliveryAddress.objects.create(**da)

                        # Populate order delivery snapshot from saved DeliveryAddress
                        try:
                            order.set_delivery_from_address(delivery_address_obj)
                        except Exception:
                            # best-effort fallback
                            order.delivery_address_text = da['formatted_address'] or da['street_address']
                            order.delivery_phone = da.get('phone', '')
                    except Exception:
                        logger.exception('Failed to create or update DeliveryAddress')
                else:
                    # Guest or not saving: populate order fields from payload
                    order.delivery_address_text = delivery_address_data.get('address', '') or delivery_address_data.get('street_name', '')
                    order.delivery_phone = delivery_address_data.get('phone') or getattr(request.user, 'phone_number', '')

                # Always set delivery instructions and special_instructions and compute ETA
                order.delivery_instructions = delivery_address_data.get('delivery_instructions', '')
                order.special_instructions = data.get('special_instructions', '')

                try:
                    # Simple ETA: baseline 10 minutes + 3 minutes per km
                    distance_km = geodesic(
                        (float(vendor_location.latitude), float(vendor_location.longitude)),
                        (float(order.delivery_latitude or delivery_address_data.get('latitude')),
                         float(order.delivery_longitude or delivery_address_data.get('longitude')))
                    ).km
                    eta_minutes = 10 + int(distance_km * 3)
                    order.estimated_delivery_time = timezone.now() + timedelta(minutes=eta_minutes)
                except Exception:
                    # ignore ETA compute errors
                    pass

                # Persist changes to order snapshot
                order.save()
            except Exception:
                logger.exception('Failed to persist delivery address or populate order snapshot')

            # Create order items and validate stock
            for cart_item in cart.items.all():
                if cart_item.product.stock_quantity < cart_item.quantity:
                    raise Exception(f"Insufficient stock for {cart_item.product.name}")

                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    unit_price=cart_item.product.price,
                    total_price=cart_item.total_price,
                    special_instructions=getattr(cart_item, 'special_instructions', '')
                )

            # Handle payment flows
            if payment_type == 'cash':
                payment = Payment.objects.create(
                    order=order,
                    user=request.user,
                    amount=order.total_amount,
                    currency='TZS',
                    payment_type='cash',
                    status='pending_admin_approval',
                    clickpesa_order_reference=f"CASH_{order.order_number}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
                )

                # Notify admin (best-effort)
                try:
                    # Send notification to admin for cash order approval
                    EmailService.send_admin_cash_order_notification(order, payment)
                except Exception:
                    logger.exception('Failed to send admin cash order notification')

                # Successful transaction; clear cart and return
                clear_cart(request)

                return Response({
                    'success': True,
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'payment_id': payment.id,
                    'status': payment.status,
                    'message': 'Cash on delivery order created. Waiting for admin approval.',
                    'payment_type': 'cash',
                    'subtotal': float(cart_total),
                    'tax_amount': float(tax_amount),
                    'delivery_fee': float(delivery_fee),
                    'total_amount': float(order.total_amount) 
                })

            elif payment_type == 'mobile_money':
                if not phone_number:
                    raise Exception('Phone number required for mobile money')

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

                # Capture cart snapshot so we can restore if payment fails later
                try:
                    cart_snapshot = [
                        {
                            'product_id': ci.product.id,
                            'quantity': ci.quantity,
                            'special_instructions': getattr(ci, 'special_instructions', '')
                        }
                        for ci in cart.items.all()
                    ]
                    payment.cart_snapshot = cart_snapshot
                    payment.save()
                except Exception:
                    # non-fatal; continue without snapshot
                    logger.exception('Failed to create cart snapshot for payment %s', getattr(payment, 'id', None))

                result = clickpesa_service.create_mobile_money_payment(
                    amount=float(order.total_amount),
                    phone_number=phone_number,
                    provider=provider,
                    order_reference=payment.clickpesa_order_reference
                )

                if not result.get('success'):
                    # Raising will rollback the transaction
                    raise Exception(result.get('error', 'Mobile money payment initiation failed'))

                # Save provider references and commit
                payment.clickpesa_payment_reference = result.get('payment_reference')
                payment.save()

                clear_cart(request)

                return Response({
                    'success': True,
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'payment_id': payment.id,
                    'status': 'pending',
                    'message': 'Order created and USSD push sent to your phone. Please complete payment.',
                    'payment_type': 'mobile_money',
                    'ussd_code': result.get('ussd_code'),
                    'subtotal': float(cart_total),
                    'tax_amount': float(tax_amount),
                    'delivery_fee': float(delivery_fee),
                    'total_amount': float(order.total_amount),
                })

            elif payment_type == 'card':
                payment = Payment.objects.create(
                    order=order,
                    user=request.user,
                    amount=order.total_amount,
                    currency='USD',
                    payment_type='card',
                    status='pending'
                )

                # Capture cart snapshot so we can restore if payment fails later
                try:
                    cart_snapshot = [
                        {
                            'product_id': ci.product.id,
                            'quantity': ci.quantity,
                            'special_instructions': getattr(ci, 'special_instructions', '')
                        }
                        for ci in cart.items.all()
                    ]
                    payment.cart_snapshot = cart_snapshot
                    payment.save()
                except Exception:
                    logger.exception('Failed to create cart snapshot for payment %s', getattr(payment, 'id', None))

                result = clickpesa_service.create_card_payment(
                    amount=float(order.total_amount),
                    order_reference=payment.clickpesa_order_reference,
                    customer_name=f"{request.user.first_name} {request.user.last_name}",
                    customer_email=request.user.email,
                    customer_phone=getattr(request.user, 'phone_number', None)
                )

                if not result.get('success'):
                    raise Exception(result.get('error', 'Card payment initiation failed'))

                payment.clickpesa_payment_reference = result.get('payment_reference')
                payment.payment_link = result.get('payment_link') or result.get('paymentLink')
                payment.save()

                clear_cart(request)

                return Response({
                    'success': True,
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'payment_id': payment.id,
                    'payment_link': payment.payment_link,
                    'status': 'pending',
                    'message': 'Order created. Please complete payment using the provided link.',
                    'payment_type': 'card',
                    'subtotal': float(cart_total),
                    'tax_amount': float(tax_amount),
                    'delivery_fee': float(delivery_fee),
                    'total_amount': float(order.total_amount),
                })

            else:
                raise Exception('Invalid payment type. Use "mobile_money", "card", or "cash"')

    except Vendor.DoesNotExist:
        return Response({'error': 'Vendor not found or not active'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Checkout error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)




@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def order_payment_status(request, order_id):
    """Return payment status for an order.

    - URL: GET /api/orders/<order_id>/payment-status/
    - Query param: refresh=true to attempt a live status check with ClickPesa
    """
    try:
        # Ensure order exists and user has access
        order = Order.objects.get(id=order_id)

        # Access control: customers can only access their orders, vendors only their orders
        if request.user.user_type == 'customer' and order.customer != request.user:
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        if request.user.user_type == 'vendor' and order.vendor != request.user:
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

        # Get latest payment for the order
        payment = Payment.objects.filter(order=order).order_by('-created_at').first()
        if not payment:
            return Response({'order_id': str(order.id), 'payment': None, 'message': 'No payment found for this order'}, status=status.HTTP_200_OK)

        # Optionally refresh from ClickPesa if requested
        refresh = str(request.query_params.get('refresh', '')).lower() in ('1', 'true', 'yes')
        if refresh and payment.payment_type in ['mobile_money', 'card'] and payment.clickpesa_order_reference:
            try:
                clickpesa_service = ClickPesaService()
                result = clickpesa_service.check_payment_status(payment.clickpesa_order_reference)
                if result.get('success'):
                    payment_data = result.get('data')
                    if isinstance(payment_data, list) and len(payment_data) > 0:
                        payment_data = payment_data[0]

                    status_str = (payment_data.get('status') or '').upper()
                    if status_str in ['SUCCESS', 'SETTLED', 'COMPLETED', 'SUCCEEDED', 'PAID']:
                        payment.status = 'succeeded'
                        payment.processed_at = timezone.now()
                        payment.clickpesa_payment_reference = payment_data.get('paymentReference') or payment.clickpesa_payment_reference
                        payment.save()

                        order.payment_status = 'paid'
                        # Do not auto-confirm order; vendor must confirm manually
                        # if order.status == 'pending':
                        #     order.status = 'confirmed'
                        order.save()

                    elif status_str == 'FAILED':
                        payment.status = 'failed'
                        payment.failure_reason = payment_data.get('message') or payment_data.get('failureReason') or 'Payment failed at gateway'
                        payment.save()

                        order.payment_status = 'failed'
                        order.status = 'cancelled'
                        order.save()

                    else:
                        payment.status = 'processing'
                        payment.save()
            except Exception as e:
                logger.warning('Live payment status refresh failed for order %s: %s', order_id, e)

        # Build response
        payload = {
            'order_id': str(order.id),
            'order_number': getattr(order, 'order_number', None),
            'payment_id': payment.id,
            'payment_type': payment.payment_type,
            'payment_status': payment.status,
            'amount': float(payment.amount) if payment.amount is not None else None,
            'currency': payment.currency,
            'payment_link': getattr(payment, 'payment_link', None),
            'clickpesa_order_reference': payment.clickpesa_order_reference,
            'clickpesa_payment_reference': getattr(payment, 'clickpesa_payment_reference', None),
            'failure_reason': getattr(payment, 'failure_reason', None),
            'processed_at': payment.processed_at,
        }

        return Response(payload, status=status.HTTP_200_OK)

    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error('Order payment status error: %s', e)
        return Response({'error': 'Failed to retrieve payment status'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def approve_cash_order(request):
    """Admin endpoint to approve or reject cash-on-delivery payments.

    Body params:
    - payment_id: UUID or PK of the Payment
    - action: 'approve' or 'reject'
    """
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
            try:
                EmailService.send_cash_order_approved_email(payment.user, order, payment)
            except Exception:
                logger.exception('Failed to send cash order approved email')

            try:
                SMSService.send_sms(
                    phone_number=getattr(payment.user, 'phone_number', None),
                    message=f"Your cash order #{order.order_number} has been approved and is being processed."
                )
            except Exception:
                logger.exception('Failed to send cash order approved SMS')

            return Response({'message': 'Cash order approved successfully'})

        elif action == 'reject':
            payment.status = 'failed'
            payment.failure_reason = 'Rejected by admin'
            order.payment_status = 'failed'
            order.status = 'cancelled'
            order.save()
            payment.save()

            # Send rejection notification
            try:
                EmailService.send_cash_order_rejected_email(payment.user, order, payment)
            except Exception:
                logger.exception('Failed to send cash order rejected email')

            try:
                SMSService.send_sms(
                    phone_number=getattr(payment.user, 'phone_number', None),
                    message=f"Your cash order #{order.order_number} has been rejected. Please contact support."
                )
            except Exception:
                logger.exception('Failed to send cash order rejected SMS')

            return Response({'message': 'Cash order rejected'})

        else:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

    except Payment.DoesNotExist:
        return Response({'error': 'Cash payment not found'}, status=status.HTTP_404_NOT_FOUND)
