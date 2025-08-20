from django.core.management.base import BaseCommand
from support.models import FAQCategory, FAQItem

class Command(BaseCommand):
    help = 'Create initial FAQ data for the support system'

    def handle(self, *args, **options):
        # Create FAQ Categories
        general_category, created = FAQCategory.objects.get_or_create(
            name='General',
            defaults={
                'description': 'General questions about our service',
                'order': 1
            }
        )
        
        orders_category, created = FAQCategory.objects.get_or_create(
            name='Orders & Delivery',
            defaults={
                'description': 'Questions about placing orders and delivery',
                'order': 2
            }
        )
        
        payments_category, created = FAQCategory.objects.get_or_create(
            name='Payments',
            defaults={
                'description': 'Payment and billing related questions',
                'order': 3
            }
        )
        
        account_category, created = FAQCategory.objects.get_or_create(
            name='Account & Profile',
            defaults={
                'description': 'Account management and profile settings',
                'order': 4
            }
        )

        # Create FAQ Items
        faq_data = [
            # General FAQs
            {
                'category': general_category,
                'question': 'What is Yum-Express?',
                'answer': 'Yum-Express is a food delivery platform that connects you with local restaurants and delivers fresh meals right to your doorstep.',
                'order': 1
            },
            {
                'category': general_category,
                'question': 'How does the delivery service work?',
                'answer': 'Simply browse restaurants, select your items, place an order, and our delivery partners will bring your food to you. You can track your order in real-time.',
                'order': 2
            },
            {
                'category': general_category,
                'question': 'What are your delivery hours?',
                'answer': 'We deliver 7 days a week from 10:00 AM to 11:00 PM. Some restaurants may have different operating hours.',
                'order': 3
            },
            
            # Orders & Delivery FAQs
            {
                'category': orders_category,
                'question': 'How do I place an order?',
                'answer': 'To place an order: 1) Browse restaurants in your area, 2) Select items and add to cart, 3) Review your order, 4) Choose payment method, 5) Confirm and track your delivery.',
                'order': 1
            },
            {
                'category': orders_category,
                'question': 'Can I modify or cancel my order?',
                'answer': 'You can modify or cancel your order within 5 minutes of placing it, provided the restaurant hasn\'t started preparing it. Contact support for assistance.',
                'order': 2
            },
            {
                'category': orders_category,
                'question': 'How long does delivery take?',
                'answer': 'Delivery typically takes 20-45 minutes depending on your location, restaurant preparation time, and current demand. You\'ll see an estimated delivery time before placing your order.',
                'order': 3
            },
            {
                'category': orders_category,
                'question': 'How can I track my order?',
                'answer': 'Once you place an order, you can track it in real-time through the app. You\'ll receive notifications when your order is confirmed, being prepared, picked up, and delivered.',
                'order': 4
            },
            
            # Payments FAQs
            {
                'category': payments_category,
                'question': 'What payment methods do you accept?',
                'answer': 'We accept all major credit cards (Visa, MasterCard, American Express), debit cards, PayPal, and digital wallets like Apple Pay and Google Pay.',
                'order': 1
            },
            {
                'category': payments_category,
                'question': 'Is it safe to pay online?',
                'answer': 'Yes, all payments are processed through secure, encrypted channels. We never store your complete card details on our servers.',
                'order': 2
            },
            {
                'category': payments_category,
                'question': 'Do you charge delivery fees?',
                'answer': 'Delivery fees vary by restaurant and distance. Any applicable delivery fees and taxes will be clearly shown before you complete your order.',
                'order': 3
            },
            
            # Account FAQs
            {
                'category': account_category,
                'question': 'How do I create an account?',
                'answer': 'You can create an account by downloading our app or visiting our website. Click "Sign Up" and provide your email, phone number, and create a password.',
                'order': 1
            },
            {
                'category': account_category,
                'question': 'How do I reset my password?',
                'answer': 'Click "Forgot Password" on the login screen, enter your email address, and we\'ll send you a link to reset your password.',
                'order': 2
            },
            {
                'category': account_category,
                'question': 'How do I update my delivery address?',
                'answer': 'Go to your profile settings and update your address information. You can also add multiple addresses for different locations.',
                'order': 3
            },
        ]

        for faq in faq_data:
            FAQItem.objects.get_or_create(
                category=faq['category'],
                question=faq['question'],
                defaults={
                    'answer': faq['answer'],
                    'order': faq['order'],
                    'is_active': True
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created FAQ data:\n'
                f'- {FAQCategory.objects.count()} categories\n'
                f'- {FAQItem.objects.count()} FAQ items'
            )
        )
