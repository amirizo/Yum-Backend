from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Authentication endpoints
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('logout/', views.logout, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    
    # Registration endpoints
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('admin/create-vendor/', views.admin_create_vendor, name='admin-create-vendor'),
    path('admin/create-driver/', views.admin_create_driver, name='admin-create-driver'),

    path('verify-otp/', views.verify_otp, name='verify-otp'),
    path('resend-otp/', views.resend_otp, name='resend-otp'),
    
    # Password management
    path('change-password/', views.change_password, name='change-password'),
    path('password-reset/', views.password_reset_request, name='password-reset'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password-reset-confirm'),
    
    # User profile
    path('profile/', views.user_profile, name='user-profile'),


    # Public Vendor Listings
    path('vendors/', views.VendorListView.as_view(), name='vendor-list'),
    
    # Vendor Profile Management
    path('vendor/profile/', views.VendorProfileView.as_view(), name='vendor-profile'),
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor-dashboard'),
    
    # Vendor Business Hours Management
    path('vendor/hours/', views.VendorBusinessHoursView.as_view(), name='vendor-business-hours'),
    path('vendor/hours/<int:pk>/', views.VendorBusinessHoursDetailView.as_view(), name='vendor-business-hours-detail'),
    
    # Vendor Location Management
    path('vendor/locations/', views.VendorLocationView.as_view(), name='vendor-locations'),
    path('vendor/locations/<uuid:pk>/', views.VendorLocationDetailView.as_view(), name='vendor-location-detail'),
    
    # Vendor Category Management
    path('vendor/categories/', views.VendorCategoryView.as_view(), name='vendor-categories'),
    path('vendor/categories/<int:pk>/', views.VendorCategoryDetailView.as_view(), name='vendor-category-detail'),
    
    # Driver Management
    path('drivers/', views.DriverListView.as_view(), name='driver-list'),
    path('drivers/location/', views.update_driver_location, name='update-driver-location'),
]
