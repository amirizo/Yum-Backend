from django.contrib import admin
from django.utils.html import format_html
from .models import (
    SupportTicket, TicketMessage, Feedback, FAQCategory, 
    FAQItem, FAQVote, SupportMetrics
)

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'subject', 'user', 'category', 'priority', 
        'status', 'assigned_to', 'created_at'
    ]
    list_filter = ['status', 'category', 'priority', 'created_at']
    search_fields = ['ticket_number', 'subject', 'user__email', 'description']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_number', 'user', 'subject', 'description', 'category')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'assigned_to')
        }),
        ('Resolution', {
            'fields': ('resolved_at', 'resolved_by'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('attachments', 'user_agent', 'ip_address'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_response_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'sender', 'message_type', 'created_at', 'is_internal']
    list_filter = ['message_type', 'is_internal', 'created_at']
    search_fields = ['ticket__ticket_number', 'sender__email', 'content']
    readonly_fields = ['created_at']

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = [
        'subject', 'user', 'feedback_type', 'rating', 'status', 'created_at'
    ]
    list_filter = ['feedback_type', 'status', 'rating', 'created_at']
    search_fields = ['subject', 'user__email', 'email', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Feedback Information', {
            'fields': ('user', 'feedback_type', 'subject', 'description', 'rating')
        }),
        ('Contact Information', {
            'fields': ('email', 'name'),
            'description': 'For anonymous feedback'
        }),
        ('Status & Response', {
            'fields': ('status', 'admin_response', 'responded_at', 'responded_by')
        }),
        ('Metadata', {
            'fields': ('user_agent', 'ip_address', 'page_url'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class FAQItemInline(admin.TabularInline):
    model = FAQItem
    extra = 0
    fields = ['question', 'answer', 'order', 'is_active']

@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'is_active', 'items_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    inlines = [FAQItemInline]
    
    def items_count(self, obj):
        return obj.faq_items.count()
    items_count.short_description = 'Items Count'

@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = [
        'question', 'category', 'order', 'is_active', 
        'views_count', 'helpful_count', 'not_helpful_count'
    ]
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['question', 'answer']
    readonly_fields = ['views_count', 'helpful_count', 'not_helpful_count', 'created_at', 'updated_at']

@admin.register(FAQVote)
class FAQVoteAdmin(admin.ModelAdmin):
    list_display = ['faq_item', 'user', 'vote', 'ip_address', 'created_at']
    list_filter = ['vote', 'created_at']
    readonly_fields = ['created_at']

@admin.register(SupportMetrics)
class SupportMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'tickets_created', 'tickets_resolved', 
        'avg_resolution_time_hours', 'feedback_submitted', 'avg_rating'
    ]
    list_filter = ['date']
    readonly_fields = ['created_at', 'updated_at']
