from rest_framework import serializers
from .models import SupportTicket, TicketMessage, Feedback, FAQCategory, FAQItem, FAQVote
from django.contrib.auth import get_user_model

User = get_user_model()

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for responses"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'user_type']

class TicketMessageSerializer(serializers.ModelSerializer):
    sender = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = TicketMessage
        fields = [
            'id', 'content', 'message_type', 'attachments', 
            'is_internal', 'created_at', 'sender'
        ]
        read_only_fields = ['id', 'created_at', 'sender']

class SupportTicketSerializer(serializers.ModelSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)
    user = UserBasicSerializer(read_only=True)
    assigned_to = UserBasicSerializer(read_only=True)
    resolved_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = SupportTicket
        fields = [
            'id', 'ticket_number', 'subject', 'description', 'category',
            'priority', 'status', 'user', 'assigned_to', 'resolved_by',
            'attachments', 'created_at', 'updated_at', 'last_response_at',
            'resolved_at', 'messages'
        ]
        read_only_fields = [
            'id', 'ticket_number', 'user', 'assigned_to', 'resolved_by',
            'created_at', 'updated_at', 'last_response_at', 'resolved_at'
        ]

class SupportTicketCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating support tickets"""
    
    class Meta:
        model = SupportTicket
        fields = [
            'subject', 'description', 'category', 'priority', 'attachments'
        ]
    
    def validate_subject(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Subject must be at least 5 characters long.")
        return value.strip()
    
    def validate_description(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Description must be at least 10 characters long.")
        return value.strip()

class SupportTicketListSerializer(serializers.ModelSerializer):
    """Simplified serializer for ticket lists"""
    user = UserBasicSerializer(read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()
    
    class Meta:
        model = SupportTicket
        fields = [
            'id', 'ticket_number', 'subject', 'category', 'priority', 
            'status', 'user', 'created_at', 'updated_at', 'last_response_at',
            'message_count', 'last_message_at'
        ]
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_last_message_at(self, obj):
        last_message = obj.messages.last()
        return last_message.created_at if last_message else obj.created_at

class TicketMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ticket messages"""
    
    class Meta:
        model = TicketMessage
        fields = ['content', 'attachments']
    
    def validate_content(self, value):
        if len(value.strip()) < 1:
            raise serializers.ValidationError("Message content cannot be empty.")
        return value.strip()

class FeedbackSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    responded_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = Feedback
        fields = [
            'id', 'feedback_type', 'subject', 'description', 'rating',
            'email', 'name', 'status', 'admin_response', 'user',
            'responded_by', 'responded_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'admin_response', 'responded_by',
            'responded_at', 'created_at', 'updated_at'
        ]

class FeedbackCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating feedback"""
    
    class Meta:
        model = Feedback
        fields = [
            'feedback_type', 'subject', 'description', 'rating',
            'email', 'name', 'page_url'
        ]
    
    def validate_subject(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Subject must be at least 3 characters long.")
        return value.strip()
    
    def validate_description(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Description must be at least 5 characters long.")
        return value.strip()
    
    def validate(self, data):
        # If user is not authenticated, require email and name
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            if not data.get('email'):
                raise serializers.ValidationError("Email is required for anonymous feedback.")
            if not data.get('name'):
                raise serializers.ValidationError("Name is required for anonymous feedback.")
        return data

class FAQItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    helpfulness_ratio = serializers.ReadOnlyField()
    
    class Meta:
        model = FAQItem
        fields = [
            'id', 'question', 'answer', 'category', 'category_name',
            'order', 'is_active', 'views_count', 'helpful_count',
            'not_helpful_count', 'helpfulness_ratio', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'views_count', 'helpful_count', 'not_helpful_count',
            'created_at', 'updated_at'
        ]

class FAQCategorySerializer(serializers.ModelSerializer):
    faq_items = FAQItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FAQCategory
        fields = [
            'id', 'name', 'description', 'icon', 'order', 'is_active',
            'created_at', 'faq_items', 'items_count'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_items_count(self, obj):
        return obj.faq_items.filter(is_active=True).count()

class FAQCategoryListSerializer(serializers.ModelSerializer):
    """Simplified serializer for category lists without items"""
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FAQCategory
        fields = [
            'id', 'name', 'description', 'icon', 'order', 'is_active',
            'items_count'
        ]
    
    def get_items_count(self, obj):
        return obj.faq_items.filter(is_active=True).count()

class FAQVoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQVote
        fields = ['vote']
    
    def validate_vote(self, value):
        if value not in ['helpful', 'not_helpful']:
            raise serializers.ValidationError("Vote must be either 'helpful' or 'not_helpful'.")
        return value

class SupportStatsSerializer(serializers.Serializer):
    """Serializer for support system statistics"""
    total_tickets = serializers.IntegerField()
    open_tickets = serializers.IntegerField()
    resolved_tickets = serializers.IntegerField()
    avg_resolution_time = serializers.DecimalField(max_digits=8, decimal_places=2)
    total_feedback = serializers.IntegerField()
    avg_feedback_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_faq_items = serializers.IntegerField()
    total_faq_views = serializers.IntegerField()
