import requests
import secrets
import string
import base64
import logging
from django.conf import settings
from django.core.mail import send_mail
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
