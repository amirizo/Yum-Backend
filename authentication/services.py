import requests
import secrets
import string
import base64
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging


logger = logging.getLogger(__name__)


class SMSService:
    @staticmethod
    def generate_temporary_password(length=8):
        """Generate a temporary password"""
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    @staticmethod
    def send_sms(phone_number, message):
        """Send SMS using Next SMS API"""
        try:
            # Ensure phone number is in correct format
            if not phone_number.startswith('+'):
                phone_number = '+255' + phone_number.lstrip('0')

            # Basic Auth
            credentials = f"{settings.NEXT_SMS_USERNAME}:{settings.NEXT_SMS_PASSWORD}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            payload = {
                'from': settings.SENDER_ID,
                'to': phone_number,
                'text': message
            }

            url = settings.NEXT_SMS_TEST_URL if settings.IS_TEST_MODE else settings.NEXT_SMS_URL
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200 and response.json().get('success', False):
                logger.info(f"SMS sent successfully to {phone_number}")
                return True, "SMS sent successfully"
            else:
                logger.error(f"Failed to send SMS to {phone_number}: {response.text}")
                return False, f"Failed to send SMS: {response.text}"

        except Exception as e:
            logger.error(f"SMS sending error: {str(e)}")
            return False, f"SMS sending error: {str(e)}"
        
    @staticmethod
    def send_temporary_password_sms(user, temporary_password):
        """Send temporary password via SMS"""
        message = f"Welcome to Yum Express! Your temporary password is: {temporary_password}. Please login and change your password immediately."
        return SMSService.send_sms(user.phone_number, message)
    

    def send_payment_success_sms(self, phone_number, order_reference, amount):
        """Send payment success SMS to customer"""
        message = f"Payment successful! Your order {order_reference} for TZS {amount:,.0f} has been confirmed. Thank you for choosing YumExpress!"
        
        return self._send_sms(phone_number, message)
    
    # def send_cash_order_sms(self, phone_number, order_reference):
    #     """Send cash order confirmation SMS"""
    #     message = f"Your cash order {order_reference} has been received and is pending admin approval. You'll be notified once approved."
        
    #     return self._send_sms(phone_number, message)
    



class EmailService:
    @staticmethod
    def send_welcome_email(user, temporary_password=None):
        """Send welcome email to new user"""
        try:
            subject = "Welcome to Yum Express"
            if temporary_password:
                message = f"""
                Welcome to Yum Express!
                
                Your account has been created successfully.
                Email: {user.email}
                Temporary Password: {temporary_password}
                
                Please login and change your password immediately for security.
                
                Best regards,
                Yum Express Team
                """
            else:
                message = f"""
                Welcome to Yum Express!
                
                Your account has been created successfully.
                Email: {user.email}
                
                Best regards,
                Yum Express Team
                """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            return True, "Email sent successfully"
            
        except Exception as e:
            logger.error(f"Email sending error: {str(e)}")
            return False, f"Email sending error: {str(e)}"
        

    @staticmethod
    def send_payment_success_email(user, order, payment):
        """Send payment success email to customer"""
        try:
            subject = f"Payment Confirmed - Order #{order.order_number}"
            
            html_message = render_to_string('emails/payment_success.html', {
                'user': user,
                'order': order,
                'payment': payment,
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Payment success email sent to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send payment success email: {str(e)}")
            return False
    
    @staticmethod
    def send_admin_cash_order_notification(order, payment):
        """Send email notification to admin about cash order - FIXED METHOD SIGNATURE"""
        try:
            subject = f'New Cash Order Requires Approval - Order #{order.id}'
            
            html_message = render_to_string('emails/admin_cash_order_confirmation.html', {
                'order': order,
                'payment': payment,
                'customer': order.customer,
                'total_amount': order.total_amount,
                'order_items': order.items.all(),
            })
            
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL_DEFAULT],  # Send to admin email
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Admin cash order notification sent for order {order.id}")
            return {'success': True, 'message': 'Admin notification sent'}
            
        except Exception as e:
            logger.error(f"Failed to send admin cash order notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_cash_order_approved_email(user, order):
        """Send cash order approval email to customer"""
        try:
            subject = f'Order Approved - Order #{order.id}'
            
            html_message = render_to_string('emails/cash_order_approved.html', {
                'user': user,
                'order': order,
                'order_items': order.items.all(),
            })
            
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Cash order approval email sent to {user.email}")
            return {'success': True, 'message': 'Cash order approval email sent'}
            
        except Exception as e:
            logger.error(f"Failed to send cash order approval email: {str(e)}")
            return {'success': False, 'error': str(e)}

        
        
        

    
