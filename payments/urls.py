from django.urls import path
from . import views

urlpatterns = [
    # Payment Methods
    path('methods/', views.PaymentMethodListView.as_view(), name='payment-method-list'),
    
    # Payment Processing
    path('create-intent/', views.create_payment_intent, name='create-payment-intent'),
    path('confirm/', views.confirm_payment, name='confirm-payment'),
    # path('mobile-money/', views.mobile_money_payment, name='mobile-money-payment'),
    path('', views.PaymentListView.as_view(), name='payment-list'),
    path('<uuid:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),

    path('admin/payments/confirm-cash-order/', views.approve_cash_order, name='confirm-cash-order'),
    
    # Refunds
    path('refunds/', views.RefundListView.as_view(), name='refund-list'),
    path('refunds/create/', views.RefundCreateView.as_view(), name='refund-create'),
    
    # Payouts
    path('payouts/', views.PayoutRequestListView.as_view(), name='payout-list'),
    
    # Webhooks
    path('webhook/clickpesa/', views.clickpesa_webhook, name='clickpesa-webhook'),
    
    # Dashboard
    path('dashboard/', views.payment_dashboard, name='payment-dashboard'),
]
