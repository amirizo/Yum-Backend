from django.contrib import admin
from django.contrib import messages
from .models import (
    PaymentMethod,
    Payment,
    Refund,
    PaymentWebhookEvent,
    PayoutRequest
)
from .views import approve_cash_order  # optional if you want to reuse logic
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from orders.services import OrderNotificationService  # Import your service

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'payment_type', 'card_brand', 'card_last4',
        'mobile_provider', 'phone_number', 'is_default', 'is_active', 'created_at'
    )
    list_filter = ('payment_type', 'is_default', 'is_active', 'created_at')
    search_fields = ('user__email', 'card_last4', 'phone_number', 'mobile_provider')
    ordering = ('-is_default', '-created_at')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'order', 'user', 'payment_type', 'amount', 'currency',
        'status', 'created_at', 'updated_at', 'processed_at'
    )
    list_filter = ('payment_type', 'status', 'currency', 'created_at')
    search_fields = (
        'id', 'order__order_number', 'user__email',
        'clickpesa_transaction_id', 'clickpesa_order_reference'
    )
    
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    actions = ['approve_cash_payments']


    actions = ['approve_cash_payments']

    @admin.action(description="Approve selected cash payments")
    def approve_cash_payments(self, request, queryset):
        for payment in queryset.filter(payment_type='cash', status='pending_admin_approval'):
            payment.status = 'succeeded'
            payment.processed_at = timezone.now()
            payment.order.payment_status = 'paid'
            payment.order.status = 'confirmed'
            payment.order.save()
            payment.save()

            # Notify customer and vendor
            OrderNotificationService.send_order_accepted_email(payment.order)
            OrderNotificationService.notify_vendor_order_delivered(payment.order)

        self.message_user(request, "Selected cash payments approved successfully.", messages.SUCCESS)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'payment', 'amount', 'currency', 'status', 'reason',
        'created_at', 'processed_at'
    )
    list_filter = ('status', 'reason', 'currency', 'created_at')
    search_fields = (
        'id', 'payment__id', 'payment__order__order_number',
        'payment__user__email'
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('clickpesa_event_id', 'event_type', 'processed', 'created_at')
    list_filter = ('event_type', 'processed', 'created_at')
    search_fields = ('clickpesa_event_id', 'event_type')
    ordering = ('-created_at',)

@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = (
        'vendor', 'amount', 'currency', 'status', 'phone_number',
        'mobile_provider', 'created_at', 'processed_at'
    )
    list_filter = ('status', 'currency', 'mobile_provider', 'created_at')
    search_fields = (
        'vendor__email', 'vendor__first_name', 'vendor__last_name', 'phone_number'
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
