from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from .models import (
    SupportTicket, TicketMessage, Feedback, FAQCategory, 
    FAQItem, FAQVote, SupportMetrics
)

User = get_user_model()

class SupportTicketAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        self.token = Token.objects.create(user=self.user)
        self.admin_token = Token.objects.create(user=self.admin_user)

    def test_create_support_ticket(self):
        """Test creating a new support ticket"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        data = {
            'subject': 'Test Issue',
            'description': 'This is a test support ticket',
            'category': 'general',
            'priority': 'medium'
        }
        
        response = self.client.post('/api/support/tickets/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SupportTicket.objects.filter(subject='Test Issue').exists())

    def test_list_user_tickets(self):
        """Test listing user's tickets"""
        SupportTicket.objects.create(
            user=self.user,
            subject='Test Ticket',
            description='Test description',
            category='general'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.get('/api/support/tickets/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_ticket_detail_and_messages(self):
        """Test retrieving ticket details with messages"""
        ticket = SupportTicket.objects.create(
            user=self.user,
            subject='Test Ticket',
            description='Test description',
            category='general'
        )
        
        TicketMessage.objects.create(
            ticket=ticket,
            sender=self.user,
            content='User message',
            message_type='message'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.get(f'/api/support/tickets/{ticket.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['messages']), 1)

class FeedbackAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)

    def test_submit_feedback_authenticated(self):
        """Test submitting feedback as authenticated user"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        data = {
            'feedback_type': 'suggestion',
            'subject': 'App Improvement',
            'description': 'Great app, could use dark mode',
            'rating': 4
        }
        
        response = self.client.post('/api/support/feedback/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_submit_feedback_anonymous(self):
        """Test submitting feedback anonymously"""
        data = {
            'feedback_type': 'bug_report',
            'subject': 'Found a bug',
            'description': 'Bug description here',
            'rating': 3,
            'email': 'anonymous@example.com',
            'name': 'Anonymous User'
        }
        
        response = self.client.post('/api/support/feedback/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

class FAQAPITestCase(APITestCase):
    def setUp(self):
        self.category = FAQCategory.objects.create(
            name='General',
            description='General questions'
        )
        self.faq_item = FAQItem.objects.create(
            category=self.category,
            question='How to place an order?',
            answer='You can place an order by...',
            order=1
        )
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)

    def test_list_faq_categories(self):
        """Test listing FAQ categories"""
        response = self.client.get('/api/support/faq/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # We now have 4 categories from the populate_faq command plus our test one
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_faq_items(self):
        """Test listing FAQ items"""
        response = self.client.get('/api/support/faq/items/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # We now have items from both the populate_faq command and our test
        self.assertGreaterEqual(len(response.data), 1)

    def test_faq_item_detail_increments_views(self):
        """Test that viewing FAQ item increments view count"""
        initial_views = self.faq_item.views_count
        
        response = self.client.get(f'/api/support/faq/items/{self.faq_item.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.faq_item.refresh_from_db()
        self.assertEqual(self.faq_item.views_count, initial_views + 1)

    def test_vote_on_faq_item(self):
        """Test voting on FAQ item"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        data = {'vote': 'helpful'}
        response = self.client.post(f'/api/support/faq/items/{self.faq_item.id}/vote/', data)
        
        # Vote endpoint returns 200 OK with vote data, not 201 CREATED
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(FAQVote.objects.filter(
            faq_item=self.faq_item,
            user=self.user,
            vote='helpful'
        ).exists())

class SupportModelsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

    def test_support_ticket_creation(self):
        """Test SupportTicket model creation and ticket number generation"""
        ticket = SupportTicket.objects.create(
            user=self.user,
            subject='Test Issue',
            description='Test description',
            category='general'
        )
        
        self.assertIsNotNone(ticket.ticket_number)
        self.assertTrue(ticket.ticket_number.startswith('TKT-'))
        self.assertEqual(ticket.status, 'open')

    def test_feedback_model(self):
        """Test Feedback model creation"""
        feedback = Feedback.objects.create(
            user=self.user,
            feedback_type='suggestion',
            subject='Test Feedback',
            description='Test description',
            rating=5
        )
        
        self.assertEqual(feedback.status, 'pending')  # Default status is 'pending'
        self.assertIsNotNone(feedback.id)

    def test_faq_category_and_item(self):
        """Test FAQ models"""
        category = FAQCategory.objects.create(
            name='Test Category',
            description='Test description'
        )
        
        faq_item = FAQItem.objects.create(
            category=category,
            question='Test Question?',
            answer='Test Answer',
            order=1
        )
        
        self.assertEqual(faq_item.views_count, 0)
        self.assertEqual(faq_item.helpful_count, 0)
        self.assertEqual(faq_item.not_helpful_count, 0)

    def test_support_metrics_model(self):
        """Test SupportMetrics model"""
        from datetime import date
        
        metrics = SupportMetrics.objects.create(
            date=date.today(),
            tickets_created=10,
            tickets_resolved=8,
            avg_resolution_time_hours=24.5,  # Use the correct field name
            feedback_submitted=5,
            avg_rating=4.2
        )
        
        self.assertEqual(metrics.avg_resolution_time_hours, 24.5)
        self.assertEqual(metrics.avg_rating, 4.2)
