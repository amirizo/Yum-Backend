from rest_framework import status, generics, permissions, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from .models import PasswordResetToken, LoginAttempt, TemporaryPassword
from .serializers import (
    UserRegistrationSerializer, AdminVendorCreationSerializer, 
    AdminDriverCreationSerializer, LoginSerializer, ChangePasswordSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer, UserSerializer, ResendOTPSerializer, OTPVerificationSerializer,
    VendorProfileSerializer, VendorProfileUpdateSerializer,
    DriverProfileSerializer, BusinessHoursSerializer, VendorLocationSerializer,
    VendorCategorySerializer
)
import logging
logger = logging.getLogger(__name__)
from .services import SMSService, EmailService
from .models import *

User = get_user_model()

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Log login attempt
            LoginAttempt.objects.create(
                email=request.data.get('email'),
                ip_address=get_client_ip(request),
                success=True,
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            })
        else:
            # Log failed login attempt
            LoginAttempt.objects.create(
                email=request.data.get('email', ''),
                ip_address=get_client_ip(request),
                success=False,
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        if request.data.get('user_type') not in ['customer', None]:
            return Response({
                'error': 'Only customer registration is allowed. Vendors and drivers must be created by admin.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create OTP record
        otp_verification = OTPVerification.objects.create(
            user=user,
            email=user.email
        )

        # Send OTP via Email
        try:
            EmailService.send_otp_email(user, otp_verification.otp_code, expiry_minutes=10)
        except Exception as e:
            logger.error(f"OTP email sending failed: {e}")
            return Response(
                {'error': 'Failed to send OTP email'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            'message': 'Registration successful. Please verify your account with the OTP sent to your email.',
            'email': user.email
        }, status=status.HTTP_201_CREATED)
    


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def admin_create_vendor(request):
    if not request.user.is_staff:
        return Response({'error': 'Only admin users can create vendors'}, status=status.HTTP_403_FORBIDDEN)

    serializer = AdminVendorCreationSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data.get('phone_number')
        
        # Check if phone number already exists
        if User.objects.filter(phone_number=phone_number).exists():
            return Response({'error': 'Phone number already exists. Please use a different number.'},
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Extract vendor-specific fields
        business_data = {
            'business_name': serializer.validated_data.pop('business_name'),
            'business_address': serializer.validated_data.pop('business_address'),
            'business_phone': serializer.validated_data.pop('business_phone'),
            'business_license': serializer.validated_data.pop('business_license', ''),
        }
        
        # Generate temporary password
        temp_password = SMSService.generate_temporary_password()
        
        # Create user
        user_data = serializer.validated_data
        user_data['user_type'] = 'vendor'
        user = User.objects.create(**user_data)
        user.set_password(temp_password)
        user.save()
        
        # Create vendor profile
        vendor_profile = Vendor.objects.create(
            user=user, 
            approved_by=request.user,
            approved_at=timezone.now(),
            **business_data
        )
        
        # Store temporary password
        TemporaryPassword.objects.create(user=user, temp_password=temp_password)
        
        # Send SMS and email
        sms_success, sms_message = SMSService.send_temporary_password_sms(user, temp_password)
        email_success, email_message = EmailService.send_welcome_email(user, temp_password)
        
        return Response({
            'message': 'Vendor created successfully',
            'user': UserSerializer(user).data,
            'sms_sent': sms_success,
            'email_sent': email_success,
            'notifications': {
                'sms': sms_message,
                'email': email_message
            }
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def admin_create_driver(request):
    if not request.user.is_staff:
        return Response({'error': 'Only admin users can create drivers'}, status=status.HTTP_403_FORBIDDEN)

    serializer = AdminDriverCreationSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data.get('phone_number')
        
        # Check if phone number already exists
        if User.objects.filter(phone_number=phone_number).exists():
            return Response({'error': 'Phone number already exists. Please use a different number.'},
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Extract driver-specific fields
        driver_data = {
            'license_number': serializer.validated_data.pop('license_number'),
            'vehicle_type': serializer.validated_data.pop('vehicle_type'),
            'vehicle_number': serializer.validated_data.pop('vehicle_number'),
        }
        
        # Generate temporary password
        temp_password = SMSService.generate_temporary_password()
        
        # Create user
        user_data = serializer.validated_data
        user_data['user_type'] = 'driver'
        user = User.objects.create(**user_data)
        user.set_password(temp_password)
        user.save()
        
        # Create driver profile
        driver_profile = Driver.objects.create(
            user=user, 
            approved_by=request.user,
            approved_at=timezone.now(),
            **driver_data
        )
        
        # Store temporary password
        TemporaryPassword.objects.create(user=user, temp_password=temp_password)
        
        # Send SMS and email
        sms_success, sms_message = SMSService.send_temporary_password_sms(user, temp_password)
        email_success, email_message = EmailService.send_welcome_email(user, temp_password)
        
        return Response({
            'message': 'Driver created successfully',
            'user': UserSerializer(user).data,
            'sms_sent': sms_success,
            'email_sent': email_success,
            'notifications': {
                'sms': sms_message,
                'email': email_message
            }
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        try:
            temp_password = TemporaryPassword.objects.get(user=user, is_used=False)
            temp_password.is_used = True
            temp_password.save()
        except TemporaryPassword.DoesNotExist:
            pass
        
        return Response({'message': 'Password changed successfully'})
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        user = User.objects.get(email=email)
        
        # Create password reset token
        reset_token = PasswordResetToken.objects.create(user=user)
        
        # Send reset email
        try:
            send_mail(
                'Password Reset - Yum Express',
                f'Reset your password by clicking this link: '
                f'http://localhost:3000/reset-password/{reset_token.token}/',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email sending failed: {e}")
        
        return Response({'message': 'Password reset email sent'})
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if serializer.is_valid():
        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']
        
        user = reset_token.user
        user.set_password(new_password)
        user.save()
        
        reset_token.is_used = True
        reset_token.save()
        
        return Response({'message': 'Password reset successfully'})
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    refresh_token = request.data.get("refresh")
    
    if not refresh_token:
        return Response(
            {"error": "Refresh token is required."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        token = RefreshToken(refresh_token)
        # Add token to blacklist if blacklist app is installed
        try:
            token.blacklist()
        except AttributeError:
            # If blacklist is not available, just return success
            # The token will still expire naturally
            pass
        return Response({"message": "Logged out successfully."})
    except TokenError as e:
        return Response(
            {"error": f"Invalid or expired token: {str(e)}"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": f"Unexpected error: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_otp(request):
    serializer = OTPVerificationSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp_code']
        
        try:
            otp_verification = OTPVerification.objects.filter(
                email=email,
                is_verified=False
            ).latest('created_at')
            
            if otp_verification.is_expired():
                return Response({
                    'error': 'OTP has expired. Please request a new one.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not otp_verification.can_attempt():
                return Response({
                    'error': 'Maximum attempts exceeded. Please request a new OTP.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            otp_verification.attempts += 1
            otp_verification.save()
            
            if otp_verification.otp_code != otp_code:
                return Response({
                    'error': f'Invalid OTP. {otp_verification.max_attempts - otp_verification.attempts} attempts remaining.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark OTP as verified
            otp_verification.is_verified = True
            otp_verification.save()
            
            # Mark user as verified
            user = otp_verification.user
            user.is_verified = True
            user.save()
            
            # Send welcome email
            try:
                html_content = render_to_string('emails/welcome.html', {
                    'first_name': user.first_name
                })
                plain_message = strip_tags(html_content)

                send_mail(
                    subject='Welcome to YumExpress!',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_content,
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"Welcome email sending failed: {e}")
            
            # Generate tokens for immediate login
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'Email verified successfully! Welcome to YumExpress.',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            })
            
        except OTPVerification.DoesNotExist:
            return Response({
                'error': 'No OTP found for this email.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def resend_otp(request):
    serializer = ResendOTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email, is_verified=False)
            
            # Create new OTP verification
            otp_verification = OTPVerification.objects.create(
                user=user,
                email=email
            )
            
            # Send OTP via Email
            try:
                html_content = render_to_string('emails/otp_verification.html', {
                    'first_name': user.first_name,
                    'otp_code': otp_verification.otp_code
                })
                plain_message = strip_tags(html_content)

                send_mail(
                    subject='Your YumExpress Verification Code',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_content,
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"OTP email sending failed: {e}")
                return Response({
                    'error': 'Failed to send OTP email.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({
                'message': 'New OTP sent successfully to your email.'
            })
            
        except User.DoesNotExist:
            return Response({
                'error': 'No unverified user found with this email.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






class VendorListView(generics.ListAPIView):
    serializer_class = VendorProfileSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['business_type', 'status', 'is_verified']
    search_fields = ['business_name', 'business_description', 'categories__name']
    ordering_fields = ['rating', 'total_orders', 'created_at']
    ordering = ['-rating', '-total_orders']
    
    def get_queryset(self):
        return Vendor.objects.filter(status='active').select_related('user').prefetch_related(
            'opening_hours', 'locations', 'categories'
        )



class VendorProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return VendorProfileSerializer
        return VendorProfileUpdateSerializer
    
    def get_object(self):
        if self.request.user.user_type != 'vendor':
            raise permissions.PermissionDenied("Only vendors can access this endpoint")
        return self.request.user.vendor_profile




class VendorBusinessHoursView(generics.ListCreateAPIView):
    serializer_class = BusinessHoursSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return BusinessHours.objects.none()
        return BusinessHours.objects.filter(vendor=self.request.user.vendor_profile)
    
    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor_profile)



class VendorBusinessHoursDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BusinessHoursSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return BusinessHours.objects.none()
        return BusinessHours.objects.filter(vendor=self.request.user.vendor_profile)



class VendorLocationView(generics.ListCreateAPIView):
    serializer_class = VendorLocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return VendorLocation.objects.none()
        return VendorLocation.objects.filter(vendor=self.request.user.vendor_profile)
    
    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor_profile)



class VendorLocationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VendorLocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return VendorLocation.objects.none()
        return VendorLocation.objects.filter(vendor=self.request.user.vendor_profile)



class VendorCategoryView(generics.ListCreateAPIView):
    serializer_class = VendorCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return VendorCategory.objects.none()
        return VendorCategory.objects.filter(vendor=self.request.user.vendor_profile)
    
    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor_profile)



class VendorCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VendorCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return VendorCategory.objects.none()
        return VendorCategory.objects.filter(vendor=self.request.user.vendor_profile)



class DriverListView(generics.ListAPIView):
    queryset = Driver.objects.filter(is_available=True)
    serializer_class = DriverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def update_driver_location(request):
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can update location'}, 
                        status=status.HTTP_403_FORBIDDEN)
    
    try:
        driver_profile = request.user.driver_profile
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')

        if not latitude or not longitude:
            return Response({'error': 'Latitude and longitude are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        driver_profile.current_latitude = latitude
        driver_profile.current_longitude = longitude
        driver_profile.last_location_update = timezone.now()
        driver_profile.save()
        
        return Response({'message': 'Location updated successfully'})
    except Driver.DoesNotExist:
        return Response({'error': 'Driver profile not found'}, 
                        status=status.HTTP_404_NOT_FOUND)



@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def vendor_dashboard(request):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        vendor_profile = request.user.vendor_profile
        
        # Import here to avoid circular imports
        from orders.models import Order, Product
        from payments.models import PayoutRequest
        
        # Get vendor statistics
        orders = Order.objects.filter(vendor=request.user)
        products = Product.objects.filter(vendor=request.user)
        payout_requests = PayoutRequest.objects.filter(vendor=request.user)
        
        # Calculate metrics
        total_orders = orders.count()
        pending_orders = orders.filter(status__in=['pending', 'confirmed']).count()
        completed_orders = orders.filter(status='delivered').count()
        total_products = products.count()
        active_products = products.filter(is_available=True).count()
        
        # Revenue calculations
        from django.db.models import Sum
        total_revenue = orders.filter(status='delivered').aggregate(
            total=Sum('total_amount'))['total'] or 0
        pending_payouts = payout_requests.filter(status='pending').aggregate(
            total=Sum('amount'))['total'] or 0
        
        return Response({
            'vendor_profile': VendorProfileSerializer(vendor_profile).data,
            'statistics': {
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'completed_orders': completed_orders,
                'total_products': total_products,
                'active_products': active_products,
                'total_revenue': float(total_revenue),
                'pending_payouts': float(pending_payouts),
                'average_rating': float(vendor_profile.rating),
                'total_reviews': vendor_profile.total_reviews,
            },
            'is_open_now': vendor_profile.is_open_now(),
            'recent_orders': []  # Will be populated when order serializer is available
        })
    except Vendor.DoesNotExist:
        return Response({'error': 'Vendor profile not found'}, 
                       status=status.HTTP_404_NOT_FOUND)
