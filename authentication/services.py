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



NEXT_SMS_STATUS_MESSAGES = {
    53: "Network not covered or not set up for your account. Contact your account manager.",
    54: "Invalid number prefix or length. Please check the number format.",
    55: "Recipient is subscribed to DND (Do Not Disturb) services.",
    56: "Sender ID not registered on your account.",
    57: "Not enough credits to send message. Please top up.",
    58: "Sender ID has been blacklisted.",
    59: "Destination number has been blacklisted.",
    60: "Prepaid package expired. Please top up to extend validity.",
    61: "Account is limited to a single test number. Contact your account manager.",
    62: "No SMS routes available on your account.",
    63: "Anti-flooding limit reached. Wait before sending more messages.",
    64: "System error occurred. Please try again later.",
    65: "Duplicate message ID. Use a unique ID for each message.",
    66: "Invalid UDH format in the message.",
    67: "Message too long (max 25 parts or 4000 bytes).",
    68: "Missing 'to' parameter. Provide a valid phone number.",
    69: "Invalid destination. Check number prefix and length."
}

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
            # Remove spaces, plus sign, and non-digit characters
            phone_number = ''.join(filter(str.isdigit, phone_number))

            # Basic validation: must be at least country code + subscriber number
            if len(phone_number) < 9:
                logger.warning(f"Invalid phone number: {phone_number}")
                return False, "Invalid phone number format"

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
                'to': phone_number,  # No '+' sign
                'text': message
            }

            url = settings.NEXT_SMS_TEST_URL if settings.IS_TEST_MODE else settings.NEXT_SMS_URL
            response = requests.post(url, headers=headers, json=payload)
            resp_json = response.json()

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
    

    @staticmethod
    def send_payment_success_sms(phone_number, order_reference=None, amount=None, **kwargs):
        """Send payment success SMS to customer.

        Accepts either `order_reference` or legacy `order_number` keyword from callers.
        Amount is optional; if provided it will be formatted.
        """
        # Support legacy callers that pass order_number instead of order_reference
        order_ref = order_reference or kwargs.get('order_number') or ''
        amt = amount if amount is not None else kwargs.get('amount')

        try:
            if amt is not None and str(amt) != '':
                # Format amount as integer TZS without decimals
                formatted_amount = f"{float(amt):,.0f}"
                message = f"Payment successful! Your order {order_ref} for TZS {formatted_amount} has been confirmed. Thank you for choosing YumExpress!"
            else:
                message = f"Payment successful! Your order {order_ref} has been confirmed. Thank you for choosing YumExpress!"
        except Exception:
            # Fallback message on any formatting error
            message = f"Payment successful! Your order {order_ref} has been confirmed. Thank you for choosing YumExpress!"

        return SMSService.send_sms(phone_number, message)

    # def send_cash_order_sms(self, phone_number, order_reference):
    #     """Send cash order confirmation SMS"""
    #     message = f"Your cash order {order_reference} has been received and is pending admin approval. You'll be notified once approved."
    #     
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
    def send_otp_email(user, otp_code, expiry_minutes=5):
        """Send OTP email for account verification or login"""
        try:
            subject = "Your OTP Code - Yum Express"

            html_message = render_to_string('emails/send_otp.html', {
                'user': user,
                'otp_code': otp_code,
                'expiry_minutes': expiry_minutes
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

            logger.info(f"OTP email sent to {user.email}")
            return True, "OTP email sent successfully"

        except Exception as e:
            logger.error(f"Failed to send OTP email: {str(e)}")
            return False, f"Failed to send OTP email: {str(e)}"
        

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
    def send_cash_order_approved_email(user, order, payment):
        """Send cash order approval email to customer"""
        try:
            subject = f'Order Approved - Order #{order.id}'
            
            html_message = render_to_string('emails/cash_order_approved.html', {
                'user': user,
                'order': order,
                'payment': payment,
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

    @staticmethod
    def send_cash_order_rejected_email(user, order, payment):
        """Send cash order rejection email to customer"""
        try:
            subject = f'Order Rejected - Order #{order.id}'
            
            html_message = render_to_string('emails/cash_order_rejected.html', {
                'user': user,
                'order': order,
                'payment': payment,
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
            
            logger.info(f"Cash order rejection email sent to {user.email}")
            return {'success': True, 'message': 'Cash order rejection email sent'}
            
        except Exception as e:
            logger.error(f"Failed to send cash order rejection email: {str(e)}")
            return {'success': False, 'error': str(e)}
            
            
    @staticmethod
    def send_admin_cash_order_notification(order, payment):
        """Send notification to admin when cash order is created"""
        try:
            subject = f'New Cash Order - Order #{order.order_number}'
            
            # Get admin emails
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_emails = list(User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True))
            
            if not admin_emails:
                logger.warning("No admin emails found for cash order notification")
                return False
            
            html_message = render_to_string('emails/admin_cash_order_notification.html', {
                'order': order,
                'payment': payment,
                'customer': order.customer,
                'order_items': order.items.all(),
            })
            
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Admin cash order notification sent for order {order.order_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send admin cash order notification: {str(e)}")
            return False



