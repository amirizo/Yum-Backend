from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .services import SMSService, EmailService
from django.contrib import messages
from django.utils.html import format_html
from .models import (
    User, Vendor, 
    Driver, 
    EmailVerificationToken,
    PasswordResetToken,
        
    UserActivity, 
    LoginAttempt, 
    TemporaryPassword, 
    OTPVerification,BusinessHours, 
    VendorLocation, VendorCategory
)


class CustomUserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'user_type', 'phone_number', 'is_active', 'created_at']
    list_filter = ['user_type', 'is_active', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'profile_image')}),
        ('Permissions', {'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'phone_number', 'user_type', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login']

    def save_model(self, request, obj, form, change):
        if not change and obj.user_type in ['driver', 'vendor']:
            # Generate temporary password
            temp_password = SMSService.generate_temporary_password()
            obj.set_password(temp_password)
            obj.save()
            
            # Send SMS with temporary password
            sms_sent, sms_msg = SMSService.send_temporary_password_sms(obj, temp_password)
            
            # Send welcome email
            email_sent, email_msg = EmailService.send_welcome_email(obj, temp_password)
            
            # Store temporary password
            TemporaryPassword.objects.create(user=obj, temp_password=temp_password)
            
            if sms_sent:
                messages.success(request, f'Temporary password sent via SMS to {obj.phone_number}')
            else:
                messages.warning(request, f'Failed to send SMS to {obj.phone_number}. Temp password: {temp_password}')
                
            if email_sent:
                messages.success(request, f'Welcome email sent to {obj.email}')
            else:
                messages.warning(request, f'Failed to send welcome email to {obj.email}')
        else:
            super().save_model(request, obj, form, change)

admin.site.register(User, CustomUserAdmin)




class BusinessHoursInline(admin.TabularInline):
    model = BusinessHours
    extra = 0

class VendorLocationInline(admin.TabularInline):
    model = VendorLocation
    extra = 0
    readonly_fields = ['created_at']

class VendorCategoryInline(admin.TabularInline):
    model = VendorCategory
    extra = 0

@admin.register(Vendor)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'business_name', 'user', 'business_type', 'status', 'is_verified', 
        'rating', 'total_orders', 'created_at'
    ]
    list_filter = [
        'business_type', 'status', 'is_verified', 'accepts_cash', 
        'accepts_card', 'accepts_mobile_money', 'created_at'
    ]
    search_fields = ['business_name', 'user__username', 'user__email', 'business_phone']
    readonly_fields = [
        'rating', 'total_orders', 'total_reviews', 'created_at', 
        'updated_at', 'approved_at', 'approved_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'business_name', 'business_type', 'business_description')
        }),
        ('Contact Information', {
            'fields': ('business_address', 'business_phone', 'business_email')
        }),
        ('Legal Information', {
            'fields': ('business_license', 'tax_id')
        }),
        ('Media', {
            'fields': ('logo', 'cover_image')
        }),
        ('Status & Verification', {
            'fields': ('status', 'is_verified', 'verification_documents', 'approved_at', 'approved_by')
        }),
        ('Business Settings', {
            'fields': (
                'delivery_fee', 'minimum_order_amount', 'delivery_radius', 
                'average_preparation_time'
            )
        }),
        ('Payment Options', {
            'fields': ('accepts_cash', 'accepts_card', 'accepts_mobile_money')
        }),
        ('Statistics', {
            'fields': ('rating', 'total_orders', 'total_reviews')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    inlines = [BusinessHoursInline, VendorLocationInline, VendorCategoryInline]
    
    actions = ['approve_vendors', 'suspend_vendors', 'activate_vendors']
    
    def approve_vendors(self, request, queryset):
        for vendor in queryset:
            vendor.approve(request.user)
        self.message_user(request, f"Approved {queryset.count()} vendors")
    approve_vendors.short_description = "Approve selected vendors"
    
    def suspend_vendors(self, request, queryset):
        queryset.update(status='suspended')
        self.message_user(request, f"Suspended {queryset.count()} vendors")
    suspend_vendors.short_description = "Suspend selected vendors"
    
    def activate_vendors(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, f"Activated {queryset.count()} vendors")
    activate_vendors.short_description = "Activate selected vendors"


@admin.register(BusinessHours)
class BusinessHoursAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'day_of_week', 'opening_time', 'closing_time', 'is_closed']
    list_filter = ['day_of_week', 'is_closed']
    search_fields = ['vendor__business_name']

@admin.register(VendorLocation)
class VendorLocationAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'name', 'city', 'is_primary', 'is_active', 'created_at']
    list_filter = ['is_primary', 'is_active', 'city', 'country']
    search_fields = ['vendor__business_name', 'name', 'address', 'city']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(VendorCategory)
class VendorCategoryAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'name', 'is_primary']
    list_filter = ['is_primary']
    search_fields = ['vendor__business_name', 'name']













@admin.register(Driver)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'vehicle_type', 'vehicle_number', 'is_available', 
        'rating', 'created_at'
    ]
    list_filter = ['is_available', 'vehicle_type', 'created_at']
    search_fields = ['user__username', 'license_number', 'vehicle_number']
    readonly_fields = [
        'rating', 'created_at', 'last_location_update'
    ]
    
    fieldsets = (
        ('Driver Information', {
            'fields': ('user', 'license_number')
        }),
        ('Vehicle Information', {
            'fields': ('vehicle_type', 'vehicle_number')
        }),
        ('Status & Location', {
            'fields': (
                'is_available', 'current_latitude', 'current_longitude',
                'last_location_update'
            )
        }),
        ('Statistics', {
            'fields': ('rating',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
   
    def get_location_display(self, obj):
        if obj.current_location_lat and obj.current_longitude:
            return format_html(
                '<a href="https://maps.google.com/?q={},{}" target="_blank">View on Map</a>',
                obj.current_location_lat, obj.current_longitude
            )
        return "No location"
    get_location_display.short_description = "Current Location"




@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'is_used', 'created_at', 'expires_at')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('token', 'created_at', 'expires_at')

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'token', 'created_at', 'expires_at', 'is_used']
    list_filter = ['is_used', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['token', 'created_at']

@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ['email', 'ip_address', 'success', 'timestamp']
    list_filter = ['success', 'timestamp']
    search_fields = ['email', 'ip_address']
    readonly_fields = ['timestamp']

@admin.register(TemporaryPassword)
class TemporaryPasswordAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'is_used']
    list_filter = ['is_used', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at']

@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'ip_address', 'created_at')
    list_filter = ('activity_type', 'created_at')
    search_fields = ('user__username', 'description', 'ip_address')
    readonly_fields = ('created_at',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'otp_code', 'is_verified', 'attempts', 'max_attempts', 'created_at', 'expires_at')
    list_filter = ('is_verified', 'created_at', 'expires_at')
    search_fields = ('user__email', 'phone_number', 'otp_code')
    readonly_fields = ('otp_code', 'created_at', 'expires_at')
    ordering = ('-created_at',)