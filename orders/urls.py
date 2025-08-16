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

    path('vendor/<int:vendor_id>/restaurant/', views.VendorRestaurantView.as_view(), name='vendor-restaurant'),
    
    # Delivery Addresses
    path('addresses/', views.DeliveryAddressListView.as_view(), name='address-list'),
    path('addresses/<int:pk>/', views.DeliveryAddressDetailView.as_view(), name='address-detail'),



    path('cart/', views.CartView.as_view(), name='cart-view'),
    path('cart/add/', views.AddToCartView.as_view(), name='add-to-cart'),
    path('cart/items/<int:pk>/', views.UpdateCartItemView.as_view(), name='update-cart-item'),
    path('cart/items/<int:pk>/remove/', views.RemoveFromCartView.as_view(), name='remove-from-cart'),
    path('cart/clear/', views.ClearCartView.as_view(), name='clear-cart'),


    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('calculate-delivery-fee/', views.calculate_delivery_fee_api, name='calculate-delivery-fee'),
    path('geocode/', views.geocode_address, name='geocode-address'),
    path('reverse-geocode/', views.reverse_geocode, name='reverse-geocode'),
    
    # Orders
    path('create/', views.OrderCreateView.as_view(), name='order-create'),
    path('', views.OrderListView.as_view(), name='order-list'),
    path('<uuid:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('<uuid:pk>/status/', views.OrderStatusUpdateView.as_view(), name='order-status-update'),
    path('<uuid:order_id>/history/', views.OrderStatusHistoryView.as_view(), name='order-status-history'),
    path('<uuid:order_id>/assign-driver/', views.assign_driver_to_order, name='assign-driver'),


    # Vendor actions
    path('<uuid:order_id>/accept/', views.vendor_accept_order, name='vendor-accept-order'),
    path('<uuid:order_id>/reject/', views.vendor_reject_order, name='vendor-reject-order'),
    
    
    # Dashboards
    path('dashboard/customer/', views.customer_dashboard, name='customer-dashboard'),
    path('dashboard/vendor/', views.vendor_dashboard, name='vendor-dashboard'),
    path('dashboard/driver/', views.driver_dashboard, name='driver-dashboard'),
]
