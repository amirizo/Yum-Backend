from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import re
from .models import User, Vendor, Driver, EmailVerificationToken, PasswordResetToken, BusinessHours, VendorLocation, VendorCategory,ContactMessage

from rest_framework import serializers




class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'password', 'password_confirm', 
                 'first_name', 'last_name', 'user_type', 'phone_number']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        # Create user without using create_user since our model doesn't have username field
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user

class AdminVendorCreationSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(max_length=200)
    business_address = serializers.CharField()
    business_phone = serializers.CharField(max_length=15)
    business_license = serializers.CharField(max_length=100, required=False)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number',
                 'business_name', 'business_address', 'business_phone', 'business_license']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

class AdminDriverCreationSerializer(serializers.ModelSerializer):
    license_number = serializers.CharField(max_length=50)
    vehicle_type = serializers.CharField(max_length=50)
    vehicle_number = serializers.CharField(max_length=20)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number',
                 'license_number', 'vehicle_type', 'vehicle_number']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            try:
                user = User.objects.get(email=email)
                user = authenticate(request=self.context.get('request'), username=email, password=password)
                if not user:
                    raise serializers.ValidationError('Invalid credentials')
                if not user.is_active:
                    raise serializers.ValidationError('Account is disabled')
            except User.DoesNotExist:
                raise serializers.ValidationError('Invalid credentials')
        else:
            raise serializers.ValidationError('Must include email and password')

        attrs['user'] = user
        return attrs

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        # Check if new password is the same as old password
        user = self.context['request'].user
        if user.check_password(value):
            raise serializers.ValidationError("New password cannot be the same as the old password.")
        
        # Use Django's built-in password validators
        validate_password(value, user=user)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        return attrs

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        
        try:
            reset_token = PasswordResetToken.objects.get(
                token=attrs['token'], 
                is_used=False
            )
            if reset_token.is_expired():
                raise serializers.ValidationError('Token has expired')
            attrs['reset_token'] = reset_token
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError('Invalid or expired token')
        
        return attrs



class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)

    def validate_otp_code(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("OTP must be exactly 6 digits")
        return value


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()




class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id','email', 'user_type', 'phone_number', 
                  'profile_image', 'is_verified', 'first_name', 'last_name',
                   'created_at', 'updated_at')
        read_only_fields = ('id', 'is_verified',   
                           'created_at', 'updated_at')


class VendorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Vendor
        fields = '__all__'







class BusinessHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHours
        fields = ['day_of_week', 'opening_time', 'closing_time', 'is_closed']

    def update(self, instance, validated_data):
        # Prevent changing vendor and day_of_week on update
        validated_data.pop("vendor", None)
        validated_data.pop("day_of_week", None)
        return super().update(instance, validated_data)



class VendorLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorLocation
        fields = ['id', 'name', 'address', 'city', 'state', 'postal_code', 
                 'country', 'latitude', 'longitude', 'is_primary', 'is_active',
                 'phone_number', 'delivery_radius', 'created_at']
        read_only_fields = ['id', 'created_at']


class VendorCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorCategory
        fields = ['name', 'description', 'is_primary']


class VendorProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    opening_hours = BusinessHoursSerializer(many=True, read_only=True)
    locations = VendorLocationSerializer(many=True, read_only=True)
    categories = VendorCategorySerializer(many=True, read_only=True)
    is_open_now = serializers.SerializerMethodField()
    primary_location = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = [
            'id', 'business_name', 'business_type', 'business_description',
            'business_address', 'business_phone', 'business_email',
            'business_license', 'tax_id', 'logo', 'cover_image', 'status',
            'is_verified', 'rating', 'total_orders', 'total_reviews',
            'delivery_fee', 'minimum_order_amount', 'delivery_radius',
            'average_preparation_time', 'accepts_cash', 'accepts_card',
            'accepts_mobile_money', 'opening_hours', 'locations', 'categories',
            'is_open_now', 'primary_location', 'created_at', 'updated_at',
            
            # user fields exposed here
            'email', 'phone_number', 'first_name', 'last_name'
        ]
        read_only_fields = [
            'id', 'status', 'is_verified', 'rating',
            'total_orders', 'total_reviews', 'created_at', 'updated_at',
            'email', 'phone_number', 'first_name', 'last_name'
        ]

    def get_is_open_now(self, obj):
        return obj.is_open_now()

    def get_primary_location(self, obj):
        primary_location = obj.locations.filter(is_primary=True).first()
        if primary_location:
            return VendorLocationSerializer(primary_location).data
        return None





class VendorProfileUpdateSerializer(serializers.ModelSerializer):
    opening_hours = BusinessHoursSerializer(many=True, required=False)
    locations = VendorLocationSerializer(many=True, required=False)
    categories = VendorCategorySerializer(many=True, required=False)
    
    class Meta:
        model = Vendor
        fields = ['business_name', 'business_type', 'business_description',
                 'business_address', 'business_phone', 'business_email',
                 'logo', 'cover_image', 'delivery_fee', 'minimum_order_amount',
                 'delivery_radius', 'average_preparation_time', 'accepts_cash',
                 'accepts_card', 'accepts_mobile_money', 'opening_hours',
                 'locations', 'categories']
    
    def update(self, instance, validated_data):
        # Handle opening hours
        opening_hours_data = validated_data.pop('opening_hours', [])
        if opening_hours_data:
            # Delete existing hours and create new ones
            instance.opening_hours.all().delete()
            for hours_data in opening_hours_data:
                BusinessHours.objects.create(vendor=instance, **hours_data)
        
        # Handle locations
        locations_data = validated_data.pop('locations', [])
        if locations_data:
            # Update or create locations
            for location_data in locations_data:
                location_id = location_data.get('id')
                if location_id:
                    # Update existing location
                    VendorLocation.objects.filter(id=location_id, vendor=instance).update(**location_data)
                else:
                    # Create new location
                    VendorLocation.objects.create(vendor=instance, **location_data)
        
        # Handle categories
        categories_data = validated_data.pop('categories', [])
        if categories_data:
            # Delete existing categories and create new ones
            instance.categories.all().delete()
            for category_data in categories_data:
                VendorCategory.objects.create(vendor=instance, **category_data)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance





class VendorProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        # Allow updating all fields, but none of them are required
        fields = [
            'business_name', 'business_type', 'business_description',
            'business_address', 'business_phone', 'business_email',
            'business_license', 'tax_id', 'logo', 'cover_image',
            'delivery_fee', 'minimum_order_amount', 'delivery_radius',
            'average_preparation_time', 'accepts_cash',
            'accepts_card', 'accepts_mobile_money',
        ]
        extra_kwargs = {field: {'required': False} for field in fields}




class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    total_orders = serializers.SerializerMethodField()
    completed_orders = serializers.SerializerMethodField()
    
    class Meta:
        model = Driver
        fields = [
            'id', 'user', 'license_number', 'vehicle_type', 'vehicle_number', 
            'vehicle_model', 'is_available', 'is_verified', 'is_online',
            'current_latitude', 'current_longitude', 'last_location_update',
            'rating', 'total_deliveries', 'created_at', 'approved_at',
            'total_orders', 'completed_orders'
        ]
        read_only_fields = [
            'user', 'is_verified', 'rating', 'total_deliveries', 
            'created_at', 'approved_at', 'current_latitude', 'current_longitude',
            'last_location_update'
        ]
    
    def get_total_orders(self, obj):
        from orders.models import Order
        return Order.objects.filter(driver=obj).count()
    
    def get_completed_orders(self, obj):
        from orders.models import Order
        return Order.objects.filter(driver=obj, status='delivered').count()


class DriverProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating driver profile"""
    
    class Meta:
        model = Driver
        fields = [
            'license_number', 'vehicle_type', 'vehicle_number', 'vehicle_model'
        ]
    
    def validate_license_number(self, value):
        if Driver.objects.filter(license_number=value).exists():
            raise serializers.ValidationError("This license number is already registered.")
        return value
    
    def validate_vehicle_number(self, value):
        if Driver.objects.filter(vehicle_number=value).exists():
            raise serializers.ValidationError("This vehicle number is already registered.")
        return value

class DriverLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8)




class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'full_name', 'email', 'phone_number', 'subject', 'message', 'created_at']


class AccountDeletionSerializer(serializers.Serializer):
    """Serializer for soft deleting user account"""
    reason = serializers.CharField(
        max_length=500, 
        required=False, 
        allow_blank=True,
        help_text="Optional reason for account deletion"
    )
    confirm_deletion = serializers.BooleanField(
        help_text="Must be true to confirm account deletion"
    )
    
    def validate_confirm_deletion(self, value):
        if not value:
            raise serializers.ValidationError("You must confirm account deletion by setting this to true.")
        return value


class AccountRestoreSerializer(serializers.Serializer):
    """Serializer for restoring soft deleted account"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        try:
            user = User.objects.get(email=email, is_deleted=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("No deleted account found with this email.")
        
        if not user.check_password(password):
            raise serializers.ValidationError("Invalid password.")
        
        attrs['user'] = user
        return attrs


class AdminAccountDeletionSerializer(serializers.Serializer):
    """Serializer for admin to delete any user account"""
    user_id = serializers.IntegerField()
    deletion_type = serializers.ChoiceField(
        choices=[('soft', 'Soft Delete'), ('hard', 'Hard Delete')],
        default='soft'
    )
    reason = serializers.CharField(
        max_length=500,
        required=True,
        help_text="Reason for admin deletion"
    )
    
    def validate_user_id(self, value):
        try:
            user = User.objects.get(id=value)
            if user.is_superuser:
                raise serializers.ValidationError("Cannot delete superuser accounts.")
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        return value


class DeletedAccountListSerializer(serializers.ModelSerializer):
    """Serializer for listing deleted accounts (admin only)"""
    days_since_deletion = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'user_type',
            'deleted_at', 'deletion_reason', 'days_since_deletion'
        ]
    
    def get_days_since_deletion(self, obj):
        if obj.deleted_at:
            from django.utils import timezone
            delta = timezone.now() - obj.deleted_at
            return delta.days
        return None