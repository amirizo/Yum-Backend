from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg, Count
from .models import (
    Category, Product, ProductImage, ProductVariant, ProductReview,
    DeliveryAddress, Order, OrderItem, OrderStatusHistory, Review
)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    readonly_fields = ['created_at']

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
        'name', 'vendor', 'category', 'price', 'status', 'is_available', 
        'inventory_display', 'rating_display', 'created_at'
    ]
    list_filter = [
        'status', 'is_available', 'is_featured', 'category', 'vendor__vendor_profile__business_type',
        'is_vegetarian', 'is_vegan', 'is_gluten_free', 'created_at'
    ]
    search_fields = ['name', 'description', 'sku', 'vendor__username', 'tags']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('vendor', 'category', 'name', 'description', 'short_description')
        }),
        ('Product Identification', {
            'fields': ('sku', 'barcode', 'tags')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_price', 'cost_price')
        }),
        ('Inventory', {
            'fields': (
                'track_inventory', 'inventory_quantity', 'low_stock_threshold', 
                'allow_backorder'
            )
        }),
        ('Physical Properties', {
            'fields': ('weight', 'unit', 'unit_size')
        }),
        ('Media', {
            'fields': ('featured_image',)
        }),
        ('Status & Availability', {
            'fields': ('status', 'is_available', 'is_featured')
        }),
        ('Restaurant Specific', {
            'fields': (
                'preparation_time', 'is_vegetarian', 'is_vegan', 
                'is_gluten_free', 'spice_level'
            )
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    inlines = [ProductImageInline, ProductVariantInline]
    
    actions = ['mark_as_available', 'mark_as_unavailable', 'mark_as_featured']
    
    def inventory_display(self, obj):
        if not obj.track_inventory:
            return "Not tracked"
        
        if obj.inventory_quantity <= 0:
            color = "red"
            status = "Out of stock"
        elif obj.is_low_stock():
            color = "orange"
            status = f"Low stock ({obj.inventory_quantity})"
        else:
            color = "green"
            status = f"In stock ({obj.inventory_quantity})"
        
        return format_html(
            '<span style="color: {};">{}</span>',
            color, status
        )
    inventory_display.short_description = "Inventory"
    
    def rating_display(self, obj):
        reviews = obj.product_reviews.filter(is_approved=True)
        if reviews.exists():
            avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
            count = reviews.count()
            return f"⭐ {avg_rating:.1f} ({count} reviews)"
        return "No reviews"
    rating_display.short_description = "Rating"
    
    def mark_as_available(self, request, queryset):
        queryset.update(is_available=True)
        self.message_user(request, f"Marked {queryset.count()} products as available")
    mark_as_available.short_description = "Mark as available"
    
    def mark_as_unavailable(self, request, queryset):
        queryset.update(is_available=False)
        self.message_user(request, f"Marked {queryset.count()} products as unavailable")
    mark_as_unavailable.short_description = "Mark as unavailable"
    
    def mark_as_featured(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, f"Marked {queryset.count()} products as featured")
    mark_as_featured.short_description = "Mark as featured"

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'alt_text', 'sort_order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['product__name', 'alt_text']

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'name', 'value', 'price_adjustment', 'inventory_quantity', 'is_active']
    list_filter = ['is_active', 'name']
    search_fields = ['product__name', 'name', 'value']

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'customer', 'rating', 'is_verified_purchase', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_verified_purchase', 'is_approved', 'created_at']
    search_fields = ['product__name', 'customer__username', 'title', 'comment']
    actions = ['approve_reviews', 'disapprove_reviews']
    
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"Approved {queryset.count()} reviews")
    approve_reviews.short_description = "Approve selected reviews"
    
    def disapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, f"Disapproved {queryset.count()} reviews")
    disapprove_reviews.short_description = "Disapprove selected reviews"

@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'label', 'city', 'country', 'is_default', 'created_at']
    list_filter = ['is_default', 'city', 'country', 'created_at']
    search_fields = ['user__username', 'street_address', 'city']
    
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
        'order_number', 'customer__username', 'customer__email',
        'vendor__username', 'vendor__vendor_profile__business_name'
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
    search_fields = ['order__order_number', 'changed_by__username', 'notes']
    readonly_fields = ['timestamp']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'customer', 'vendor', 'overall_rating', 
        'food_rating', 'delivery_rating', 'created_at'
    ]
    list_filter = ['overall_rating', 'food_rating', 'delivery_rating', 'created_at']
    search_fields = [
        'order__order_number', 'customer__username', 
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
