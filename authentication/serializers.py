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
    user = UserSerializer(read_only=True)
    opening_hours = BusinessHoursSerializer(many=True, read_only=True)
    locations = VendorLocationSerializer(many=True, read_only=True)
    categories = VendorCategorySerializer(many=True, read_only=True)
    is_open_now = serializers.SerializerMethodField()
    primary_location = serializers.SerializerMethodField()
    
    class Meta:
        model = Vendor
        fields = ['id', 'user', 'business_name', 'business_type', 'business_description',
                 'business_address', 'business_phone', 'business_email', 'business_license',
                 'tax_id', 'logo', 'cover_image', 'status', 'is_verified', 'rating',
                 'total_orders', 'total_reviews', 'delivery_fee', 'minimum_order_amount',
                 'delivery_radius', 'average_preparation_time', 'accepts_cash',
                 'accepts_card', 'accepts_mobile_money', 'opening_hours', 'locations',
                 'categories', 'is_open_now', 'primary_location', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'status', 'is_verified', 'rating', 
                           'total_orders', 'total_reviews', 'created_at', 'updated_at']
    
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





class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Driver
        fields = '__all__'

class DriverLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8)




class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'full_name', 'email', 'phone_number', 'subject', 'message', 'created_at']