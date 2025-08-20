from rest_framework import generics, status, permissions, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    SupportTicket, TicketMessage, Feedback, FAQCategory, 
    FAQItem, FAQVote, SupportMetrics
)
from .serializers import (
    SupportTicketSerializer, SupportTicketCreateSerializer, SupportTicketListSerializer,
    TicketMessageSerializer, TicketMessageCreateSerializer,
    FeedbackSerializer, FeedbackCreateSerializer,
    FAQCategorySerializer, FAQCategoryListSerializer,
    FAQItemSerializer, FAQVoteSerializer, SupportStatsSerializer
)

User = get_user_model()

# Support Ticket Views
class SupportTicketListCreateView(generics.ListCreateAPIView):
    """List and create support tickets"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'priority']
    search_fields = ['subject', 'description', 'ticket_number']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'admin':
            return SupportTicket.objects.all().select_related('user', 'assigned_to', 'resolved_by')
        else:
            return SupportTicket.objects.filter(user=user).select_related('assigned_to', 'resolved_by')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SupportTicketCreateSerializer
        return SupportTicketListSerializer
    
    def perform_create(self, serializer):
        # Get client IP and user agent for metadata
        ip_address = self.request.META.get('REMOTE_ADDR')
        user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        
        serializer.save(
            user=self.request.user,
            ip_address=ip_address,
            user_agent=user_agent
        )

class SupportTicketDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve and update support ticket details"""
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'admin':
            return SupportTicket.objects.all().select_related(
                'user', 'assigned_to', 'resolved_by'
            ).prefetch_related('messages__sender')
        else:
            return SupportTicket.objects.filter(user=user).select_related(
                'assigned_to', 'resolved_by'
            ).prefetch_related('messages__sender')

class TicketMessageListCreateView(generics.ListCreateAPIView):
    """List and create messages for a specific ticket"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        ticket_id = self.kwargs['ticket_id']
        user = self.request.user
        
        # Check if user has access to this ticket
        if user.user_type == 'admin':
            ticket = SupportTicket.objects.filter(id=ticket_id).first()
        else:
            ticket = SupportTicket.objects.filter(id=ticket_id, user=user).first()
        
        if not ticket:
            return TicketMessage.objects.none()
        
        # Return messages, excluding internal notes for non-admin users
        messages = ticket.messages.select_related('sender')
        if user.user_type != 'admin':
            messages = messages.filter(is_internal=False)
        
        return messages
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TicketMessageCreateSerializer
        return TicketMessageSerializer
    
    def perform_create(self, serializer):
        ticket_id = self.kwargs['ticket_id']
        user = self.request.user
        
        # Get the ticket and verify access
        if user.user_type == 'admin':
            ticket = SupportTicket.objects.filter(id=ticket_id).first()
        else:
            ticket = SupportTicket.objects.filter(id=ticket_id, user=user).first()
        
        if not ticket:
            return Response({'error': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Determine message type
        message_type = 'admin_response' if user.user_type == 'admin' else 'user_message'
        
        # Update ticket status if needed
        if message_type == 'user_message' and ticket.status == 'pending_user':
            ticket.status = 'open'
        elif message_type == 'admin_response' and ticket.status == 'open':
            ticket.status = 'in_progress'
        
        ticket.last_response_at = timezone.now()
        ticket.save()
        
        serializer.save(
            ticket=ticket,
            sender=user,
            message_type=message_type
        )

# Feedback Views
class FeedbackListCreateView(generics.ListCreateAPIView):
    """List and create feedback"""
    permission_classes = [permissions.AllowAny]  # Allow anonymous feedback
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['feedback_type', 'status', 'rating']
    search_fields = ['subject', 'description']
    ordering_fields = ['created_at', 'rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.user_type == 'admin':
            return Feedback.objects.all().select_related('user', 'responded_by')
        elif user.is_authenticated:
            return Feedback.objects.filter(user=user).select_related('responded_by')
        else:
            return Feedback.objects.none()  # Anonymous users can't list feedback
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return FeedbackCreateSerializer
        return FeedbackSerializer
    
    def perform_create(self, serializer):
        # Get client IP and user agent for metadata
        ip_address = self.request.META.get('REMOTE_ADDR')
        user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        
        # Set user if authenticated
        user = self.request.user if self.request.user.is_authenticated else None
        
        serializer.save(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent
        )

class FeedbackDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve and update feedback (admin only for updates)"""
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'admin':
            return Feedback.objects.all().select_related('user', 'responded_by')
        else:
            return Feedback.objects.filter(user=user).select_related('responded_by')
    
    def update(self, request, *args, **kwargs):
        # Only admins can update feedback
        if request.user.user_type != 'admin':
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        return super().update(request, *args, **kwargs)

# FAQ Views
class FAQCategoryListView(generics.ListAPIView):
    """List FAQ categories"""
    serializer_class = FAQCategoryListSerializer
    permission_classes = [permissions.AllowAny]
    queryset = FAQCategory.objects.filter(is_active=True).prefetch_related('faq_items')
    ordering = ['order', 'name']

class FAQCategoryDetailView(generics.RetrieveAPIView):
    """Get FAQ category with all its items"""
    serializer_class = FAQCategorySerializer
    permission_classes = [permissions.AllowAny]
    queryset = FAQCategory.objects.filter(is_active=True).prefetch_related(
        'faq_items'
    )

class FAQItemListView(generics.ListAPIView):
    """List FAQ items, optionally filtered by category"""
    serializer_class = FAQItemSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['question', 'answer']
    ordering = ['category__order', 'order', 'question']
    
    def get_queryset(self):
        return FAQItem.objects.filter(
            is_active=True,
            category__is_active=True
        ).select_related('category')

class FAQItemDetailView(generics.RetrieveAPIView):
    """Get FAQ item details and increment view count"""
    serializer_class = FAQItemSerializer
    permission_classes = [permissions.AllowAny]
    queryset = FAQItem.objects.filter(is_active=True).select_related('category')
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Increment view count
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def vote_faq_item(request, item_id):
    """Vote on FAQ item helpfulness"""
    try:
        faq_item = FAQItem.objects.get(id=item_id, is_active=True)
    except FAQItem.DoesNotExist:
        return Response({'error': 'FAQ item not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = FAQVoteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    vote = serializer.validated_data['vote']
    ip_address = request.META.get('REMOTE_ADDR')
    user = request.user if request.user.is_authenticated else None
    
    # Check if user/IP has already voted
    existing_vote = FAQVote.objects.filter(
        faq_item=faq_item,
        ip_address=ip_address
    ).first()
    
    if user:
        existing_vote = FAQVote.objects.filter(
            faq_item=faq_item,
            user=user
        ).first()
    
    if existing_vote:
        # Update existing vote
        old_vote = existing_vote.vote
        existing_vote.vote = vote
        existing_vote.save()
        
        # Update counters
        if old_vote != vote:
            if old_vote == 'helpful':
                faq_item.helpful_count -= 1
                faq_item.not_helpful_count += 1
            else:
                faq_item.not_helpful_count -= 1
                faq_item.helpful_count += 1
            faq_item.save()
    else:
        # Create new vote
        FAQVote.objects.create(
            faq_item=faq_item,
            user=user,
            ip_address=ip_address,
            vote=vote
        )
        
        # Update counters
        if vote == 'helpful':
            faq_item.helpful_count += 1
        else:
            faq_item.not_helpful_count += 1
        faq_item.save()
    
    return Response({
        'message': 'Vote recorded successfully',
        'helpful_count': faq_item.helpful_count,
        'not_helpful_count': faq_item.not_helpful_count,
        'helpfulness_ratio': faq_item.helpfulness_ratio
    })

# Statistics and Analytics
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def support_statistics(request):
    """Get support system statistics"""
    if request.user.user_type != 'admin':
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    # Ticket statistics
    total_tickets = SupportTicket.objects.count()
    open_tickets = SupportTicket.objects.filter(status__in=['open', 'in_progress']).count()
    resolved_tickets = SupportTicket.objects.filter(status='resolved').count()
    
    # Average resolution time (in hours)
    resolved_tickets_with_time = SupportTicket.objects.filter(
        status='resolved',
        resolved_at__isnull=False
    )
    avg_resolution_time = 0
    if resolved_tickets_with_time.exists():
        total_resolution_time = sum([
            (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
            for ticket in resolved_tickets_with_time
        ])
        avg_resolution_time = total_resolution_time / resolved_tickets_with_time.count()
    
    # Feedback statistics
    total_feedback = Feedback.objects.count()
    avg_feedback_rating = Feedback.objects.filter(
        rating__isnull=False
    ).aggregate(avg=Avg('rating'))['avg'] or 0
    
    # FAQ statistics
    total_faq_items = FAQItem.objects.filter(is_active=True).count()
    total_faq_views = FAQItem.objects.aggregate(
        total=Count('views_count')
    )['total'] or 0
    
    stats_data = {
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'resolved_tickets': resolved_tickets,
        'avg_resolution_time': round(avg_resolution_time, 2),
        'total_feedback': total_feedback,
        'avg_feedback_rating': round(float(avg_feedback_rating), 2),
        'total_faq_items': total_faq_items,
        'total_faq_views': total_faq_views,
    }
    
    serializer = SupportStatsSerializer(stats_data)
    return Response(serializer.data)

# Utility views
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def support_categories(request):
    """Get available support categories"""
    categories = [
        {'value': choice[0], 'label': choice[1]}
        for choice in SupportTicket.CATEGORY_CHOICES
    ]
    return Response({'categories': categories})

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def feedback_types(request):
    """Get available feedback types"""
    feedback_types = [
        {'value': choice[0], 'label': choice[1]}
        for choice in Feedback.FEEDBACK_TYPES
    ]
    return Response({'feedback_types': feedback_types})
