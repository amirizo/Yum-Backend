from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg, Count
from .models import (
    Category, Product, ProductVariant,
    DeliveryAddress, Order, OrderItem, OrderStatusHistory, Review
)

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    readonly_fields = ['created_at']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'is_active', 'product_count', 'created_at']
    list_filter = ['is_active', 'category_type', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    def product_count(self, obj):
        return obj.products.filter(status='active').count()
    product_count.short_description = "Active Products"

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'vendor', 'category', 'price', 'is_available', 
        'stock_quantity', 'created_at'
    ]
    list_filter = [
        'is_available', 'category', 'vendor__vendor_profile__business_type',
        'created_at'
    ]
    search_fields = ['name', 'description', 'vendor__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('vendor', 'category', 'name', 'description')
        }),
        ('Pricing', {
            'fields': ('price',)
        }),
        ('Inventory', {
            'fields': ('stock_quantity', 'unit')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Status & Availability', {
            'fields': ('is_available',)
        }),
        ('Restaurant Specific', {
            'fields': ('preparation_time',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    inlines = [ProductVariantInline]
    
    actions = ['mark_as_available', 'mark_as_unavailable']
    
    def mark_as_available(self, request, queryset):
        queryset.update(is_available=True)
        self.message_user(request, f"Marked {queryset.count()} products as available")
    mark_as_available.short_description = "Mark as available"
    
    def mark_as_unavailable(self, request, queryset):
        queryset.update(is_available=False)
        self.message_user(request, f"Marked {queryset.count()} products as unavailable")
    mark_as_unavailable.short_description = "Mark as unavailable"


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'name', 'value', 'price_adjustment', 'inventory_quantity', 'is_active']
    list_filter = ['is_active', 'name']
    search_fields = ['product__name', 'name', 'value']



@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'label', 'city', 'country', 'is_default', 'created_at']
    list_filter = ['is_default', 'city', 'country', 'created_at']
    search_fields = ['user__email', 'street_address', 'city']
    
    def get_map_link(self, obj):
        if obj.latitude and obj.longitude:
            return format_html(
                '<a href="https://maps.google.com/?q={},{}" target="_blank">View on Map</a>',
                obj.latitude, obj.longitude
            )
        return "No coordinates"
    get_map_link.short_description = "Map"

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['total_price']

class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ['timestamp']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'customer', 'vendor', 'status', 'payment_status',
        'total_amount', 'created_at'
    ]
    list_filter = [
        'status', 'payment_status', 'vendor__vendor_profile__business_type', 'created_at'
    ]
    search_fields = [
        'order_number', 'customer__email', 'customer__email',
        'vendor__email', 'vendor__vendor_profile__business_name'
    ]
    readonly_fields = [
        'order_number', 'subtotal', 'delivery_fee', 'tax_amount', 'total_amount',
        'created_at', 'updated_at', 'confirmed_at', 'delivered_at'
    ]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'vendor', 'driver')
        }),
        ('Status', {
            'fields': ('status', 'payment_status')
        }),
        ('Delivery Information', {
            'fields': ('delivery_address', 'delivery_instructions', 'estimated_delivery_time', 'actual_delivery_time')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'delivery_fee', 'tax_amount', 'total_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'confirmed_at', 'delivered_at')
        }),
    )
    
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    actions = ['mark_as_confirmed', 'mark_as_preparing', 'mark_as_ready']
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='confirmed')
        self.message_user(request, f"Confirmed {updated} orders")
    mark_as_confirmed.short_description = "Mark as confirmed"
    
    def mark_as_preparing(self, request, queryset):
        updated = queryset.filter(status='confirmed').update(status='preparing')
        self.message_user(request, f"Marked {updated} orders as preparing")
    mark_as_preparing.short_description = "Mark as preparing"
    
    def mark_as_ready(self, request, queryset):
        updated = queryset.filter(status='preparing').update(status='ready')
        self.message_user(request, f"Marked {updated} orders as ready")
    mark_as_ready.short_description = "Mark as ready"



@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'status', 'changed_by', 'timestamp']
    list_filter = ['status', 'timestamp']
    search_fields = ['order__order_number', 'changed_by__email', 'notes']
    readonly_fields = ['timestamp']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'customer', 'vendor', 'overall_rating', 
        'food_rating', 'delivery_rating', 'created_at'
    ]
    list_filter = ['overall_rating', 'food_rating', 'delivery_rating', 'created_at']
    search_fields = [
        'order__order_number', 'customer__email', 
        'vendor__vendor_profile__business_name', 'comment'
    ]
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Review Information', {
            'fields': ('order', 'customer', 'vendor', 'driver')
        }),
        ('Ratings', {
            'fields': ('overall_rating', 'food_rating', 'delivery_rating')
        }),
        ('Comments', {
            'fields': ('comment',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
