from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Authentication endpoints
    path('login', views.CustomTokenObtainPairView.as_view(), name='login'),  # no slash
    path('logout', views.logout, name='logout'),
    path('token/refresh', TokenRefreshView.as_view(), name='token-refresh'),

    # Registration
    path('register', views.UserRegistrationView.as_view(), name='register'),
    path('admin/create-vendor/', views.admin_create_vendor, name='admin-create-vendor'),
    path('admin/create-driver/', views.admin_create_driver, name='admin-create-driver'),

    # OTP
    path('verify-otp', views.verify_otp, name='verify-otp'),
    path('resend-otp', views.resend_otp, name='resend-otp'),

    # Password
    path('change-password', views.change_password, name='change-password'),
    path('password-reset', views.password_reset_request, name='password-reset'),
    path('password-reset/confirm', views.password_reset_confirm, name='password-reset-confirm'),

    # Profile
    path('profile', views.user_profile, name='user-profile'),
    path('contact-us/', views.contact_us, name='contact-us'),

    # Vendor Listings
    path('vendors', views.VendorListView.as_view(), name='vendor-list'),

    # Vendor Profile
    path('vendor/profile', views.VendorProfileView.as_view(), name='vendor-profile'),
    path('vendor/dashboard', views.vendor_dashboard, name='vendor-dashboard'),

    # Vendor Hours
    path('vendor/hours', views.VendorBusinessHoursView.as_view(), name='vendor-business-hours'),
    path('vendor/hours/<int:pk>', views.VendorBusinessHoursDetailView.as_view(), name='vendor-business-hours-detail'),

    # Vendor Locations
    path('vendor/locations', views.VendorLocationView.as_view(), name='vendor-locations'),
    path('vendor/locations/<uuid:pk>', views.VendorLocationDetailView.as_view(), name='vendor-location-detail'),

    # Vendor Categories
    path('vendor/categories', views.VendorCategoryView.as_view(), name='vendor-categories'),
    path('vendor/categories/<int:pk>', views.VendorCategoryDetailView.as_view(), name='vendor-category-detail'),

    # Drivers
    path('drivers', views.DriverListView.as_view(), name='driver-list'),
    path('drivers/location', views.update_driver_location, name='update-driver-location'),
]

