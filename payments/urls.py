from django.urls import path
from . import views

urlpatterns = [
    # Payment Methods
    path('methods/', views.PaymentMethodListView.as_view(), name='payment-method-list'),
    
    # Payment Processing
    path('create-order-and-payment/', views.create_order_and_payment, name='create-order-and-payment'),
    # path('create-intent/', views.create_payment_intent, name='create-payment-intent'),
    # path('confirm/', views.confirm_payment, name='confirm-payment'),
    # path('status/<uuid:payment_id>/', views.check_payment_status, name='check-payment-status'),
    
    # Payment Records
    path('', views.PaymentListView.as_view(), name='payment-list'),
    path('<uuid:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),

    # Admin Actions
    path('admin/payments/confirm-cash-order/', views.approve_cash_order, name='confirm-cash-order'),
    
    # Refunds
    path('refunds/', views.RefundListView.as_view(), name='refund-list'),
    path('refunds/create/', views.RefundCreateView.as_view(), name='refund-create'),
    
    # Payouts
    path('payouts/', views.PayoutRequestListView.as_view(), name='payout-list'),
    
    # Webhooks
    path('checkout/', views.checkout, name='checkout'),
    path('webhook/clickpesa/', views.clickpesa_webhook, name='clickpesa-webhook'),
    # path('confirm/', views.confirm_payment, name='confirm-payment'),

    # Order payment status (client-facing)
    path('order/<str:order_id>/payment-status/', views.order_payment_status, name='order-payment-status'),

    # Dashboard
    path('dashboard/', views.payment_dashboard, name='payment-dashboard'),
]
