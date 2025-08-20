from django.urls import path
from . import views

urlpatterns = [
    # Support Tickets
    path('tickets/', views.SupportTicketListCreateView.as_view(), name='support-tickets'),
    path('tickets/<uuid:pk>/', views.SupportTicketDetailView.as_view(), name='support-ticket-detail'),
    path('tickets/<uuid:ticket_id>/messages/', views.TicketMessageListCreateView.as_view(), name='ticket-messages'),
    
    # Feedback
    path('feedback/', views.FeedbackListCreateView.as_view(), name='feedback'),
    path('feedback/<uuid:pk>/', views.FeedbackDetailView.as_view(), name='feedback-detail'),
    
    # FAQ
    path('faq/categories/', views.FAQCategoryListView.as_view(), name='faq-categories'),
    path('faq/categories/<int:pk>/', views.FAQCategoryDetailView.as_view(), name='faq-category-detail'),
    path('faq/categories/<int:pk>/items/', views.FAQItemListView.as_view(), name='faq-category-items'),
    path('faq/items/', views.FAQItemListView.as_view(), name='faq-items'),
    path('faq/items/<int:pk>/', views.FAQItemDetailView.as_view(), name='faq-item-detail'),
    path('faq/items/<int:item_id>/vote/', views.vote_faq_item, name='faq-vote'),
    
    # Statistics and Utilities
    path('statistics/', views.support_statistics, name='support-statistics'),
    path('categories/', views.support_categories, name='support-categories'),
    path('feedback-types/', views.feedback_types, name='feedback-types'),
]
