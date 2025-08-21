from rest_framework import status, generics, permissions, filters
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from django.db import models
from .models import PasswordResetToken, LoginAttempt, TemporaryPassword
from .serializers import (
    UserRegistrationSerializer, AdminVendorCreationSerializer, 
    AdminDriverCreationSerializer, LoginSerializer, ChangePasswordSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer, UserSerializer, ResendOTPSerializer, OTPVerificationSerializer,
    VendorProfileSerializer, VendorProfileUpdateSerializer,
    DriverProfileSerializer, DriverProfileCreateSerializer, BusinessHoursSerializer, VendorLocationSerializer,
    VendorCategorySerializer, ContactMessageSerializer,VendorProfileUpdateSerializer,
    AccountDeletionSerializer, DeletedAccountListSerializer, AdminAccountDeletionSerializer, AccountRestoreSerializer
)
import logging
logger = logging.getLogger(__name__)
from .services import SMSService, EmailService
from .models import *
from django.core.mail import EmailMultiAlternatives

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


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def user_profile(request):
    user = request.user

    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response(serializer.data)

    # Always allow partial updates, even for PUT
    serializer = UserSerializer(user, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])  # Allows file upload & JSON
def update_user_profile(request):
    """
    Update the authenticated user's profile.
    - PUT: Update all fields (replace existing data)
    - PATCH: Update only provided fields
    """
    user = request.user
    serializer = UserSerializer(user, data=request.data, partial=(request.method == 'PATCH'))

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



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
            raise PermissionDenied(detail="Only vendors can access this endpoint")
        return self.request.user.vendor_profile

    def update(self, request, *args, **kwargs):
        # Allow partial updates automatically
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)





class VendorBusinessHoursView(generics.ListCreateAPIView):
    serializer_class = BusinessHoursSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access business hours.")
        return BusinessHours.objects.filter(vendor=self.request.user.vendor_profile)
    
   


    def perform_create(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can create business hours.")
        vendor = self.request.user.vendor_profile
        day = serializer.validated_data.get("day_of_week")
        

        BusinessHours.objects.update_or_create(
            vendor=vendor,
            day_of_week=day,
            defaults={
                "opening_time": serializer.validated_data.get("opening_time"),
                "closing_time": serializer.validated_data.get("closing_time"),
            },
        )



class VendorBusinessHoursDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BusinessHoursSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow vendors to see their own business hours
        if self.request.user.user_type != 'vendor':
            return BusinessHours.objects.none()
        return BusinessHours.objects.filter(vendor=self.request.user.vendor_profile)

    def get_serializer(self, *args, **kwargs):
        # On update/partial_update, make fields not required
        if self.request.method in ['PUT', 'PATCH']:
            kwargs['partial'] = True  # allows partial updates
        return super().get_serializer(*args, **kwargs)

    def perform_update(self, serializer):
        # Ensure the vendor field is always set correctly
        serializer.save(vendor=self.request.user.vendor_profile)
    
    


    



class VendorLocationView(generics.ListCreateAPIView):
    serializer_class = VendorLocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access this resource.")
        return VendorLocation.objects.filter(vendor=self.request.user.vendor_profile)
    
    def perform_create(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can create locations.")
        serializer.save(vendor=self.request.user.vendor_profile)


class VendorLocationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VendorLocationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            # Non-vendors cannot access
            return VendorLocation.objects.none()
        return VendorLocation.objects.filter(vendor=self.request.user.vendor_profile)

    def update(self, request, *args, **kwargs):
        if request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can update locations.")
        # Allow partial updates (don't require all fields)
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)



class VendorCategoryView(generics.ListCreateAPIView):
    serializer_class = VendorCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access categories.")
        return VendorCategory.objects.filter(vendor=self.request.user.vendor_profile)

    def perform_create(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can create categories.")
        serializer.save(vendor=self.request.user.vendor_profile)



class VendorCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VendorCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return VendorCategory.objects.none()
        return VendorCategory.objects.filter(vendor=self.request.user.vendor_profile)

    def update(self, request, *args, **kwargs):
        if request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can update categories.")
        # Allow partial updates (fields are not required)
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)



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
        vendor = request.user.vendor_profile

        from orders.models import Order, Product
        from payments.models import PayoutRequest
        from django.db.models import Sum

        # ✅ These models are linked to Vendor
        orders = Order.objects.filter(vendor=vendor)
        products = Product.objects.filter(vendor=vendor)
        payout_requests = PayoutRequest.objects.filter(vendor=vendor)

        # Stats
        total_orders = orders.count()
        pending_orders = orders.filter(status__in=['pending', 'confirmed']).count()
        completed_orders = orders.filter(status='delivered').count()
        total_products = products.count()
        active_products = products.filter(is_available=True).count()

        # Revenue
        total_revenue = orders.filter(status='delivered').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        pending_payouts = payout_requests.filter(status='pending').aggregate(
            total=Sum('amount')
        )['total'] or 0

        return Response({
            'vendor_profile': VendorProfileSerializer(vendor).data,
            'statistics': {
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'completed_orders': completed_orders,
                'total_products': total_products,
                'active_products': active_products,
                'total_revenue': float(total_revenue),
                'pending_payouts': float(pending_payouts),
                'average_rating': float(vendor.rating or 0),
                'total_reviews': vendor.total_reviews,
            },
            'is_open_now': vendor.is_open_now(),
            'recent_orders': []  # TODO: hook up serializer
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)






@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def contact_us(request):
    serializer = ContactMessageSerializer(data=request.data)
    if serializer.is_valid():
        contact = serializer.save()

        # Subject for admin
        subject = f"[Contact Us] 📩 Message from {contact.full_name}"

        # Plain text fallback
        text_content = f"""
        You have received a new contact message:

        Full Name: {contact.full_name}
        Email: {contact.email}
        Phone Number: {contact.phone_number}
        Subject: {contact.subject}

        Message:
        {contact.message}
        """

        try:
            # -------------------------
            # Admin email
            # -------------------------
            html_content_admin = render_to_string("emails/contact_message_admin.html", {
                "full_name": contact.full_name,
                "email": contact.email,
                "phone_number": contact.phone_number,
                "subject": contact.subject,
                "message": contact.message,
            })

            email = EmailMultiAlternatives(
                subject,
                text_content,
                settings.DEFAULT_FROM_EMAIL,
                [admin_email for _, admin_email in settings.ADMINS]
            )
            email.attach_alternative(html_content_admin, "text/html")
            email.send()

            # -------------------------
            # User confirmation email
            # -------------------------
            confirmation_subject = "✅ We received your message"
            confirmation_message = f"""
            Hi {contact.full_name},

            Thank you for contacting us. We’ve received your message:
            "{contact.message}"

            Our team will get back to you shortly.

            Regards,
            The Support Team
            """

            html_content_user = render_to_string("emails/contact_message_user.html", {
                "full_name": contact.full_name,
                "subject": contact.subject,
                "message": contact.message,
            })

            confirmation_email = EmailMultiAlternatives(
                confirmation_subject,
                confirmation_message,
                settings.DEFAULT_FROM_EMAIL,
                [contact.email]
            )
            confirmation_email.attach_alternative(html_content_user, "text/html")
            confirmation_email.send()

        except Exception as e:
            return Response(
                {"error": f"Message saved but failed to send email: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({"success": "Your message has been sent successfully!"}, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DriverProfileView(generics.RetrieveUpdateAPIView):
    """
    Driver profile view for retrieving and updating driver information
    """
    serializer_class = DriverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        if self.request.user.user_type != 'driver':
            raise PermissionDenied("Only drivers can access driver profile.")
        
        try:
            return self.request.user.driver_profile
        except Driver.DoesNotExist:
            raise NotFound("Driver profile not found.")
    
    def update(self, request, *args, **kwargs):
        if request.user.user_type != 'driver':
            raise PermissionDenied("Only drivers can update driver profile.")
        
        # Allow partial updates
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class DriverProfileCreateView(generics.CreateAPIView):
    """
    Create driver profile for authenticated users
    """
    serializer_class = DriverProfileCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        if self.request.user.user_type != 'driver':
            raise PermissionDenied("Only users with driver type can create driver profile.")
        
        # Check if driver profile already exists
        if hasattr(self.request.user, 'driver_profile'):
            raise ValidationError("Driver profile already exists for this user.")
        
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def driver_dashboard(request):
    """
    Driver dashboard with statistics and current status
    """
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can access driver dashboard'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    try:
        driver_profile = request.user.driver_profile
        
        # Get driver statistics
        from orders.models import Order
        
        total_orders = Order.objects.filter(driver=driver_profile).count()
        completed_orders = Order.objects.filter(driver=driver_profile, status='delivered').count()
        in_progress_orders = Order.objects.filter(
            driver=driver_profile, 
            status__in=['picked_up', 'in_transit']
        ).count()
        
        # Calculate completion rate
        completion_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0
        
        # Get recent orders
        recent_orders = Order.objects.filter(driver=driver_profile).order_by('-created_at')[:5]
        
        # Get earnings (you can implement this based on your payment model)
        # For now, we'll calculate based on completed orders and delivery fees
        total_earnings = Order.objects.filter(
            driver=driver_profile, 
            status='delivered'
        ).aggregate(
            total=models.Sum('delivery_fee')
        )['total'] or 0
        
        return Response({
            'driver_info': DriverProfileSerializer(driver_profile).data,
            'statistics': {
                'total_orders': total_orders,
                'completed_orders': completed_orders,
                'in_progress_orders': in_progress_orders,
                'completion_rate': round(completion_rate, 2),
                'total_earnings': total_earnings,
                'average_rating': driver_profile.rating
            },
            'status': {
                'is_online': driver_profile.is_online,
                'is_available': driver_profile.is_available,
                'is_verified': driver_profile.is_verified,
                'last_location_update': driver_profile.last_location_update
            }
        })
        
    except Driver.DoesNotExist:
        return Response({'error': 'Driver profile not found'}, 
                       status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_driver_availability(request):
    """
    Toggle driver availability status
    """
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can toggle availability'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    try:
        driver_profile = request.user.driver_profile
        
        # Toggle availability
        driver_profile.is_available = not driver_profile.is_available
        
        # If going offline, also set is_online to False
        if not driver_profile.is_available:
            driver_profile.is_online = False
        
        driver_profile.save()
        
        return Response({
            'message': f'Driver availability set to {"available" if driver_profile.is_available else "unavailable"}',
            'is_available': driver_profile.is_available,
            'is_online': driver_profile.is_online
        })
        
    except Driver.DoesNotExist:
        return Response({'error': 'Driver profile not found'}, 
                       status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_driver_online_status(request):
    """
    Toggle driver online/offline status
    """
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can toggle online status'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    try:
        driver_profile = request.user.driver_profile
        
        # Toggle online status
        driver_profile.is_online = not driver_profile.is_online
        
        # If going online, must be available
        if driver_profile.is_online and not driver_profile.is_available:
            driver_profile.is_available = True
        
        driver_profile.save()
        
        return Response({
            'message': f'Driver is now {"online" if driver_profile.is_online else "offline"}',
            'is_online': driver_profile.is_online,
            'is_available': driver_profile.is_available
        })
        
    except Driver.DoesNotExist:
        return Response({'error': 'Driver profile not found'}, 
                       status=status.HTTP_404_NOT_FOUND)


# =============================================================================
# ACCOUNT DELETION APIS
# =============================================================================

class AccountSoftDeleteView(generics.GenericAPIView):
    """Soft delete user account (can be restored)"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AccountDeletionSerializer
    
    def post(self, request):
        """Soft delete the authenticated user's account"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        reason = serializer.validated_data.get('reason', 'User requested account deletion')
        
        # Check if account is already deleted
        if user.is_deleted:
            return Response({
                'error': 'Account is already deleted'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Perform soft delete
        user.soft_delete(reason=reason)
        
        # Log the activity
        from .models import UserActivity
        UserActivity.objects.create(
            user=user,
            activity_type='account_deletion',
            description=f'Account soft deleted. Reason: {reason}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Logout user by deleting their token
        try:
            from rest_framework.authtoken.models import Token
            Token.objects.filter(user=user).delete()
        except:
            pass
        
        return Response({
            'message': 'Account has been successfully deleted. You can restore it within 30 days by contacting support.',
            'deleted_at': user.deleted_at,
            'can_restore_until': user.deleted_at + timezone.timedelta(days=30) if user.deleted_at else None
        }, status=status.HTTP_200_OK)


class AccountHardDeleteView(generics.GenericAPIView):
    """Permanently delete user account (cannot be restored)"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AccountDeletionSerializer
    
    def delete(self, request):
        """Permanently delete the authenticated user's account"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user_email = user.email
        user_id = user.id
        
        # Log the activity before deletion
        from .models import UserActivity
        UserActivity.objects.create(
            user=user,
            activity_type='account_hard_deletion',
            description='Account permanently deleted by user',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Delete all related data
        # Note: Some related objects might need special handling based on your business logic
        try:
            # Delete authentication tokens
            from rest_framework.authtoken.models import Token
            Token.objects.filter(user=user).delete()
            
            # Delete user account permanently
            user.delete()
            
        except Exception as e:
            return Response({
                'error': 'Failed to delete account. Please contact support.',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'message': f'Account {user_email} has been permanently deleted.',
            'deleted_user_id': user_id
        }, status=status.HTTP_200_OK)


class AccountRestoreView(generics.GenericAPIView):
    """Restore a soft deleted account"""
    permission_classes = [permissions.AllowAny]
    serializer_class = AccountRestoreSerializer
    
    def post(self, request):
        """Restore a soft deleted account"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Check if account can still be restored (within 30 days)
        if user.deleted_at:
            days_since_deletion = (timezone.now() - user.deleted_at).days
            if days_since_deletion > 30:
                return Response({
                    'error': 'Account cannot be restored. Deletion period has expired (>30 days).'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Restore the account
        user.restore_account()
        
        # Log the activity
        from .models import UserActivity
        UserActivity.objects.create(
            user=user,
            activity_type='account_restoration',
            description='Account restored from soft deletion',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Create new authentication token
        from rest_framework.authtoken.models import Token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'Account has been successfully restored.',
            'token': token.key,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'user_type': user.user_type
            }
        }, status=status.HTTP_200_OK)


class AdminAccountManagementView(generics.GenericAPIView):
    """Admin endpoints for managing user accounts"""
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return DeletedAccountListSerializer
        return AdminAccountDeletionSerializer
    
    def get(self, request):
        """List all deleted accounts (admin only)"""
        deleted_users = User.objects.filter(is_deleted=True).order_by('-deleted_at')
        
        # Filter by days since deletion if provided
        days_filter = request.query_params.get('days')
        if days_filter:
            try:
                days = int(days_filter)
                cutoff_date = timezone.now() - timezone.timedelta(days=days)
                deleted_users = deleted_users.filter(deleted_at__gte=cutoff_date)
            except ValueError:
                pass
        
        serializer = self.get_serializer(deleted_users, many=True)
        return Response({
            'deleted_accounts': serializer.data,
            'total_count': deleted_users.count()
        })
    
    def post(self, request):
        """Admin delete any user account"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_id = serializer.validated_data['user_id']
        deletion_type = serializer.validated_data['deletion_type']
        reason = serializer.validated_data['reason']
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if deletion_type == 'soft':
            if user.is_deleted:
                return Response({
                    'error': 'User account is already soft deleted'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user.soft_delete(reason=f"Admin deletion: {reason}")
            
            # Log admin activity
            from .models import UserActivity
            UserActivity.objects.create(
                user=user,
                activity_type='admin_soft_deletion',
                description=f'Account soft deleted by admin {request.user.email}. Reason: {reason}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return Response({
                'message': f'User {user.email} has been soft deleted by admin.',
                'deletion_type': 'soft',
                'deleted_at': user.deleted_at
            })
        
        elif deletion_type == 'hard':
            user_email = user.email
            
            # Log admin activity before deletion
            from .models import UserActivity
            UserActivity.objects.create(
                user=user,
                activity_type='admin_hard_deletion',
                description=f'Account permanently deleted by admin {request.user.email}. Reason: {reason}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Delete user permanently
            user.delete()
            
            return Response({
                'message': f'User {user_email} has been permanently deleted by admin.',
                'deletion_type': 'hard'
            })


class AdminAccountRestoreView(generics.GenericAPIView):
    """Admin restore any soft deleted account"""
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request, user_id):
        """Admin restore a soft deleted account"""
        try:
            user = User.objects.get(id=user_id, is_deleted=True)
        except User.DoesNotExist:
            return Response({
                'error': 'Deleted user not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Restore the account
        user.restore_account()
        
        # Log admin activity
        from .models import UserActivity
        UserActivity.objects.create(
            user=user,
            activity_type='admin_account_restoration',
            description=f'Account restored by admin {request.user.email}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'message': f'User {user.email} has been successfully restored by admin.',
            'restored_user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'user_type': user.user_type,
                'restored_at': timezone.now()
            }
        })


class AccountDeletionStatusView(generics.GenericAPIView):
    """Check account deletion status"""
    permission_classes = [permissions.AllowAny]  # Allow checking status even for deleted accounts
    
    def get(self, request):
        """Get account deletion status by email or for authenticated user"""
        # Check if user is authenticated
        if request.user.is_authenticated:
            user = request.user
        else:
            # Allow checking by email for deleted accounts
            email = request.query_params.get('email')
            if not email:
                return Response({
                    'error': 'Email parameter required for unauthenticated requests'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
        
        if not user.is_deleted:
            return Response({
                'is_deleted': False,
                'message': 'Account is active'
            })
        
        days_since_deletion = (timezone.now() - user.deleted_at).days if user.deleted_at else 0
        can_restore = days_since_deletion <= 30
        
        return Response({
            'is_deleted': True,
            'deleted_at': user.deleted_at,
            'deletion_reason': user.deletion_reason,
            'days_since_deletion': days_since_deletion,
            'can_restore': can_restore,
            'restore_deadline': user.deleted_at + timezone.timedelta(days=30) if user.deleted_at else None
        })