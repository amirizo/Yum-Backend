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
]
