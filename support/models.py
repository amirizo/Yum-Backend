from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()

class SupportTicket(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('pending_user', 'Pending User Response'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    CATEGORY_CHOICES = [
        ('technical', 'Technical Issue'),
        ('billing', 'Billing & Payments'),
        ('account', 'Account Issues'),
        ('order', 'Order Problems'),
        ('delivery', 'Delivery Issues'),
        ('feature_request', 'Feature Request'),
        ('general', 'General Inquiry'),
        ('bug_report', 'Bug Report'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    
    # Ticket details
    subject = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Assignment and resolution
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_tickets',
        limit_choices_to={'user_type': 'admin'}
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_tickets'
    )
    
    # Metadata
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_response_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            # Generate ticket number: TKT-YYYYMMDD-XXXX
            from django.utils import timezone
            import random
            import string
            today = timezone.now().strftime('%Y%m%d')
            random_part = ''.join(random.choices(string.digits, k=4))
            self.ticket_number = f"TKT-{today}-{random_part}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.ticket_number} - {self.subject}"
    
    class Meta:
        ordering = ['-created_at']


class TicketMessage(models.Model):
    MESSAGE_TYPES = [
        ('user_message', 'User Message'),
        ('admin_response', 'Admin Response'),
        ('system_note', 'System Note'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='user_message')
    
    content = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    is_internal = models.BooleanField(default=False)  # Internal notes not visible to user
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Message for {self.ticket.ticket_number} by {self.sender.email}"
    
    class Meta:
        ordering = ['created_at']


class Feedback(models.Model):
    FEEDBACK_TYPES = [
        ('bug_report', 'Bug Report'),
        ('feature_request', 'Feature Request'),
        ('general_feedback', 'General Feedback'),
        ('complaint', 'Complaint'),
        ('compliment', 'Compliment'),
        ('suggestion', 'Suggestion'),
    ]
    
    RATING_CHOICES = [
        (1, '1 Star - Very Poor'),
        (2, '2 Stars - Poor'),
        (3, '3 Stars - Average'),
        (4, '4 Stars - Good'),
        (5, '5 Stars - Excellent'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('implemented', 'Implemented'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedback', null=True, blank=True)
    
    # Feedback content
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, default='general_feedback')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    rating = models.IntegerField(
        choices=RATING_CHOICES, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Contact info for anonymous feedback
    email = models.EmailField(blank=True)
    name = models.CharField(max_length=100, blank=True)
    
    # Status and response
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_response = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responded_feedback'
    )
    
    # Metadata
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    page_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.feedback_type} - {self.subject}"
    
    class Meta:
        ordering = ['-created_at']


class FAQCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or name")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = "FAQ Categories"


class FAQItem(models.Model):
    category = models.ForeignKey(FAQCategory, on_delete=models.CASCADE, related_name='faq_items')
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Metadata
    views_count = models.PositiveIntegerField(default=0)
    helpful_count = models.PositiveIntegerField(default=0)
    not_helpful_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return self.question
    
    @property
    def helpfulness_ratio(self):
        total_votes = self.helpful_count + self.not_helpful_count
        if total_votes == 0:
            return 0
        return (self.helpful_count / total_votes) * 100
    
    class Meta:
        ordering = ['category', 'order', 'question']


class FAQVote(models.Model):
    VOTE_CHOICES = [
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
    ]
    
    faq_item = models.ForeignKey(FAQItem, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    vote = models.CharField(max_length=15, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['faq_item', 'user'], ['faq_item', 'ip_address']]


class SupportMetrics(models.Model):
    """Model to track support system metrics"""
    date = models.DateField(unique=True)
    
    # Ticket metrics
    tickets_created = models.PositiveIntegerField(default=0)
    tickets_resolved = models.PositiveIntegerField(default=0)
    tickets_closed = models.PositiveIntegerField(default=0)
    avg_resolution_time_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Feedback metrics
    feedback_submitted = models.PositiveIntegerField(default=0)
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # FAQ metrics
    faq_views = models.PositiveIntegerField(default=0)
    faq_helpful_votes = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Support metrics for {self.date}"
    
    class Meta:
        ordering = ['-date']
