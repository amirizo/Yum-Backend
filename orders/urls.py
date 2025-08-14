from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    
    # Products - Public
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    
    # Product Reviews
    path('products/<int:product_id>/reviews/', views.ProductReviewListView.as_view(), name='product-review-list'),
    
    # Vendor Product Management
    path('vendor/products/', views.VendorProductListView.as_view(), name='vendor-product-list'),
    path('vendor/products/<int:pk>/', views.VendorProductDetailView.as_view(), name='vendor-product-detail'),
    path('vendor/products/bulk-update/', views.bulk_update_product_status, name='vendor-product-bulk-update'),
    path('vendor/products/analytics/', views.vendor_product_analytics, name='vendor-product-analytics'),
    
    # Product Images
    path('vendor/products/<int:product_id>/images/', views.ProductImageListView.as_view(), name='product-image-list'),
    path('vendor/products/images/<int:pk>/', views.ProductImageDetailView.as_view(), name='product-image-detail'),
    
    # Product Variants
    path('vendor/products/<int:product_id>/variants/', views.ProductVariantListView.as_view(), name='product-variant-list'),
    path('vendor/products/variants/<int:pk>/', views.ProductVariantDetailView.as_view(), name='product-variant-detail'),
    
    # Delivery Addresses
    path('addresses/', views.DeliveryAddressListView.as_view(), name='address-list'),
    path('addresses/<int:pk>/', views.DeliveryAddressDetailView.as_view(), name='address-detail'),
    
    # Orders - General
    path('create/', views.OrderCreateView.as_view(), name='order-create'),
    path('', views.OrderListView.as_view(), name='order-list'),
    path('<uuid:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('<uuid:pk>/status/', views.OrderStatusUpdateView.as_view(), name='order-status-update'),
    path('<uuid:order_id>/history/', views.OrderStatusHistoryView.as_view(), name='order-status-history'),
    path('<uuid:pk>/assign-driver/', views.assign_driver_to_order, name='assign-driver'),
    
    # Vendor Order Management
    path('vendor/orders/', views.VendorOrderListView.as_view(), name='vendor-order-list'),
    path('vendor/orders/<uuid:pk>/', views.VendorOrderDetailView.as_view(), name='vendor-order-detail'),
    path('<uuid:order_id>/accept/', views.accept_order, name='accept-order'),
    path('<uuid:order_id>/reject/', views.reject_order, name='reject-order'),
    path('vendor/orders/<uuid:order_id>/update-status/', views.vendor_update_preparation_status, name='vendor-update-preparation-status'),
    path('vendor/orders/bulk-update/', views.bulk_update_order_status, name='vendor-bulk-update-orders'),
    path('vendor/orders/queue/', views.vendor_order_queue, name='vendor-order-queue'),
    path('vendor/orders/analytics/', views.vendor_order_analytics, name='vendor-order-analytics'),
    path('vendor/orders/daily-summary/', views.vendor_daily_summary, name='vendor-daily-summary'),
    
    
    # # Reviews
    path('<uuid:order_id>/review/', views.OrderReviewCreateView.as_view(), name='order-review-create'),
    path('reviews/', views.ReviewListView.as_view(), name='review-list'),
    
    # Dashboards
    path('dashboard/customer/', views.customer_dashboard, name='customer-dashboard'),
    path('dashboard/vendor/', views.vendor_dashboard, name='vendor-dashboard'),
    path('dashboard/driver/', views.driver_dashboard, name='driver-dashboard'),
]
