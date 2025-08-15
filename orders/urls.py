from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    
    # Products
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('vendor/products/', views.VendorProductListView.as_view(), name='vendor-product-list'),
    path('vendor/products/<int:pk>/', views.VendorProductDetailView.as_view(), name='vendor-product-detail'),
    
    # Delivery Addresses
    path('addresses/', views.DeliveryAddressListView.as_view(), name='address-list'),
    path('addresses/<int:pk>/', views.DeliveryAddressDetailView.as_view(), name='address-detail'),
    

    # Orders
    path('create/', views.OrderCreateView.as_view(), name='order-create'),
    path('', views.OrderListView.as_view(), name='order-list'),
    path('<uuid:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('<uuid:pk>/status/', views.OrderStatusUpdateView.as_view(), name='order-status-update'),
    path('<uuid:order_id>/history/', views.OrderStatusHistoryView.as_view(), name='order-status-history'),
    path('<uuid:order_id>/assign-driver/', views.assign_driver_to_order, name='assign-driver'),
    
    
    # Dashboards
    path('dashboard/customer/', views.customer_dashboard, name='customer-dashboard'),
    path('dashboard/vendor/', views.vendor_dashboard, name='vendor-dashboard'),
    path('dashboard/driver/', views.driver_dashboard, name='driver-dashboard'),
]
