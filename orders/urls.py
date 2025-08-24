from django.urls import path
from . import views
from . import delivery_views
from . import test_delivery

urlpatterns = [
    # Categories
    path('product/categories/', views.CategoryListView.as_view(), name='category-list'),
    
    # Vendor Category Management
    path('vendor/categories/', views.VendorCategoryListCreateView.as_view(), name='vendor-category-list-create'),
    path('vendor/categories/<int:pk>/', views.VendorCategoryDetailView.as_view(), name='vendor-category-detail'),
    path('vendor/categories/stats/', views.VendorCategoryStatsView.as_view(), name='vendor-category-stats'),
    
    # Products
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('vendor/products/', views.VendorProductListView.as_view(), name='vendor-product-list'),
    path('vendor/orders/', views.VendorOrdersView.as_view(), name='vendor-orders'),
    path('vendor/products/<int:pk>/', views.VendorProductDetailView.as_view(), name='vendor-product-detail'),
    
    path('vendor/<int:vendor_id>/restaurant/', views.VendorRestaurantView.as_view(), name='vendor-restaurant'),
    
    # Delivery Addresses
    path('addresses/', delivery_views.SavedDeliveryAddressListView.as_view(), name='address-list'),
    path('addresses/<int:pk>/', delivery_views.SavedDeliveryAddressDetailView.as_view(), name='address-detail'),
    path('addresses/validate/', delivery_views.validate_delivery_address, name='validate-address'),
    path('delivery/calculate/', delivery_views.calculate_delivery_preview, name='calculate-delivery'),

    # Cart Management
    path('cart/', views.CartView.as_view(), name='cart-view'),
    path('cart/add/', views.AddToCartView.as_view(), name='add-to-cart'),
    path('cart/items/<int:pk>/', views.UpdateCartItemView.as_view(), name='update-cart-item'),
    path('cart/items/<int:pk>/remove/', views.RemoveFromCartView.as_view(), name='remove-from-cart'),
    path('cart/clear/', views.ClearCartView.as_view(), name='clear-cart'),

    # Checkout & Payment Flow
    # path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('calculate-delivery-fee/', views.calculate_delivery_fee_api, name='calculate-delivery-fee'),
    path('geocode/', views.geocode_address, name='geocode-address'),
    path('reverse-geocode/', views.reverse_geocode, name='reverse-geocode'),
    
    # Testing Endpoints
    path('test/delivery-calculations/', test_delivery.test_delivery_calculations, name='test-delivery-calculations'),
    path('test/custom-delivery/', test_delivery.custom_delivery_test, name='custom-delivery-test'),
    
    # Orders
    path('create/', views.OrderCreateView.as_view(), name='order-create'),
    path('', views.OrderListView.as_view(), name='order-list'),
    path('<uuid:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('<uuid:pk>/status/', views.OrderStatusUpdateView.as_view(), name='order-status-update'),
    path('<uuid:order_id>/history/', views.OrderStatusHistoryView.as_view(), name='order-status-history'),
    path('<uuid:order_id>/assign-driver/', views.assign_driver_to_order, name='assign-driver'),

    # Customer order management
    path('customer/history/', views.CustomerOrderHistoryView.as_view(), name='customer-order-history'),
    path('<uuid:order_id>/cancel/', views.CancelOrderView.as_view(), name='cancel-order'),
    path('<uuid:order_id>/refund/', views.RequestRefundView.as_view(), name='request-refund'),
    path('<uuid:order_id>/reorder/', views.ReorderFromOrderView.as_view(), name='reorder-from-order'),


    # Vendor actions
    path('<uuid:order_id>/accept/', views.vendor_accept_order, name='vendor-accept-order'),
    path('<uuid:order_id>/reject/', views.vendor_reject_order, name='vendor-reject-order'),
    path('<uuid:order_id>/preparing/', views.vendor_set_preparing, name='vendor-set-preparing'),
    path('<uuid:order_id>/ready/', views.vendor_set_ready, name='vendor-set-ready'),
    
    # Driver actions
    path('available-for-drivers/', views.available_orders_for_drivers, name='available-orders-drivers'),
    path('driver/deliveries/', views.driver_deliveries, name='driver-deliveries'),
    path('<uuid:order_id>/assign-driver/', views.assign_driver_to_order, name='assign-driver'),
    path('<uuid:order_id>/delivered/', views.driver_mark_delivered, name='driver-mark-delivered'),
    path('<uuid:order_id>/update-location/', views.driver_update_location, name='driver-update-location'),
    
    
    # Dashboards
    path('dashboard/customer/', views.customer_dashboard, name='customer-dashboard'),
    path('dashboard/vendor/', views.vendor_dashboard, name='vendor-dashboard'),
    path('dashboard/driver/', views.driver_dashboard, name='driver-dashboard'),
]
