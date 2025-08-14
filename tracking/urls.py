from django.urls import path
from . import views

urlpatterns = [
    # Driver location tracking
    path('location/update/', views.DriverLocationUpdateView.as_view(), name='location-update'),
    path('location/history/', views.DriverLocationHistoryView.as_view(), name='location-history'),
    
    # Order tracking
    path('order/<int:order_id>/', views.OrderTrackingDetailView.as_view(), name='order-tracking-detail'),
    path('order/<int:order_id>/start/', views.start_delivery_tracking, name='start-delivery-tracking'),
    path('order/<int:order_id>/end/', views.end_delivery_tracking, name='end-delivery-tracking'),
    path('order/<int:order_id>/status/', views.update_order_status, name='update-order-status'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    
    # Admin/dispatch
    path('drivers/nearby/', views.get_nearby_drivers, name='nearby-drivers'),
]
