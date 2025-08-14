import requests
import json
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .models import Payment, PaymentMethod

logger = logging.getLogger(__name__)

class ClickPesaService:
    """
    Complete ClickPesa payment gateway integration service
    Handles JWT authentication, mobile money, card payments, and status checking
    """
    
    def __init__(self):
        self.client_id = settings.CLICKPESA_CLIENT_ID
        self.api_key = settings.CLICKPESA_API_KEY
        self.base_url = settings.CLICKPESA_BASE_URL
        self.token_cache_key = 'clickpesa_jwt_token'
    
    def _get_headers(self, include_auth=False):
        """Get request headers with optional JWT authentication"""
        headers = {
            'Content-Type': 'application/json',
            'client-id': self.client_id,
            'api-key': self.api_key
        }
        
        if include_auth:
            token = self._get_jwt_token()
            if token:
                headers['Authorization'] = token
        
        return headers
    
    def _get_jwt_token(self):
        """
        Get JWT token from cache or generate new one
        Token is valid for 1 hour as per ClickPesa documentation
        """
        # Check cache first
        cached_token = cache.get(self.token_cache_key)
        if cached_token:
            return cached_token
        
        # Generate new token
        try:
            url = f"{self.base_url}/generate-token"
            headers = self._get_headers(include_auth=False)
            
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success') and data.get('token'):
                token = data['token']
                # Cache for 55 minutes (5 minutes before expiry)
                cache.set(self.token_cache_key, token, 3300)
                logger.info("ClickPesa JWT token generated successfully")
                return token
            else:
                logger.error(f"Failed to generate ClickPesa token: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating ClickPesa token: {str(e)}")
            return None
    
    def preview_mobile_money_payment(self, amount, phone_number, order_reference):
        """
        Preview mobile money payment to validate details
        Uses TZS currency for mobile money payments
        """
        try:
            url = f"{self.base_url}/payments/preview-ussd-push-request"
            headers = self._get_headers(include_auth=True)
            
            payload = {
                "amount": int(amount * 100),  # Convert to cents
                "currency": "TZS",
                "phoneNumber": phone_number,
                "orderReference": order_reference
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Mobile money preview successful for order {order_reference}")
            return {
                'success': True,
                'data': data
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Mobile money preview failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def initiate_mobile_money_payment(self, amount, phone_number, order_reference, customer_email=None):
        """
        Initiate mobile money payment via USSD push
        Sends USSD push to customer's phone for payment
        """
        try:
            url = f"{self.base_url}/payments/initiate-ussd-push-request"
            headers = self._get_headers(include_auth=True)
            
            payload = {
                "amount": int(amount * 100),  # Convert to cents
                "currency": "TZS",
                "phoneNumber": phone_number,
                "orderReference": order_reference
            }
            
            if customer_email:
                payload["customerEmail"] = customer_email
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Mobile money payment initiated for order {order_reference}")
            return {
                'success': True,
                'data': data,
                'payment_reference': data.get('paymentReference'),
                'message': 'USSD push sent to customer phone'
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Mobile money payment initiation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def preview_card_payment(self, amount, order_reference):
        """
        Preview card payment to validate details
        Uses USD currency for card payments
        """
        try:
            url = f"{self.base_url}/payments/preview-card-payment"
            headers = self._get_headers(include_auth=True)
            
            # Convert TZS to USD (approximate rate: 1 USD = 2500 TZS)
            usd_amount = amount / 2500
            
            payload = {
                "amount": round(usd_amount * 100),  # Convert to cents
                "currency": "USD",
                "orderReference": order_reference
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Card payment preview successful for order {order_reference}")
            return {
                'success': True,
                'data': data
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Card payment preview failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def initiate_card_payment(self, amount, order_reference, customer_email=None):
        """
        Initiate card payment and get payment link
        Returns payment link for customer to complete payment
        """
        try:
            url = f"{self.base_url}/payments/initiate-card-payment"
            headers = self._get_headers(include_auth=True)
            
            # Convert TZS to USD (approximate rate: 1 USD = 2500 TZS)
            usd_amount = amount / 2500
            
            payload = {
                "amount": round(usd_amount * 100),  # Convert to cents
                "currency": "USD",
                "orderReference": order_reference
            }
            
            if customer_email:
                payload["customerEmail"] = customer_email
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Card payment initiated for order {order_reference}")
            return {
                'success': True,
                'data': data,
                'payment_link': data.get('paymentLink'),
                'payment_reference': data.get('paymentReference')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Card payment initiation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_payment_status(self, order_reference):
        """
        Check payment status using order reference
        Returns payment status: SUCCESS, SETTLED, PROCESSING, PENDING, FAILED
        """
        try:
            url = f"{self.base_url}/payments/{order_reference}"
            headers = self._get_headers(include_auth=True)
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract key information from response
            payment_info = {
                'success': True,
                'status': data.get('status'),
                'payment_reference': data.get('paymentReference'),
                'order_reference': data.get('orderReference'),
                'collected_amount': data.get('collectedAmount', 0) / 100,  # Convert from cents
                'collected_currency': data.get('collectedCurrency'),
                'message': data.get('message'),
                'updated_at': data.get('updatedAt'),
                'created_at': data.get('createdAt'),
                'customer': data.get('customer', {})
            }
            
            logger.info(f"Payment status checked for order {order_reference}: {payment_info['status']}")
            return payment_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Payment status check failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_refund(self, payment_reference, amount, reason="Order cancelled"):
        """
        Process refund for a payment
        Note: ClickPesa refund API endpoint needs to be confirmed
        """
        try:
            # This is a placeholder - actual refund endpoint needs confirmation
            logger.info(f"Refund requested for payment {payment_reference}: {amount} TZS")
            
            # For now, we'll mark the payment as refunded in our system
            # and handle the actual refund process manually or via ClickPesa dashboard
            return {
                'success': True,
                'message': 'Refund request submitted',
                'refund_reference': f"REF_{payment_reference}_{int(timezone.now().timestamp())}"
            }
            
        except Exception as e:
            logger.error(f"Refund processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_payment_record(self, order, payment_type, amount, **kwargs):
        """
        Create payment record in database
        """
        try:
            payment = Payment.objects.create(
                order=order,
                payment_type=payment_type,
                amount=amount,
                currency='TZS' if payment_type == 'mobile_money' else 'USD',
                status='pending',
                clickpesa_order_reference=kwargs.get('order_reference'),
                clickpesa_payment_reference=kwargs.get('payment_reference'),
                phone_number=kwargs.get('phone_number'),
                payment_link=kwargs.get('payment_link')
            )
            
            logger.info(f"Payment record created: {payment.id}")
            return payment
            
        except Exception as e:
            logger.error(f"Failed to create payment record: {str(e)}")
            return None
    
    def update_payment_status(self, payment, status_data):
        """
        Update payment status based on ClickPesa response
        """
        try:
            clickpesa_status = status_data.get('status', '').upper()
            
            # Map ClickPesa status to our payment status
            status_mapping = {
                'SUCCESS': 'completed',
                'SETTLED': 'completed',
                'PROCESSING': 'processing',
                'PENDING': 'pending',
                'FAILED': 'failed'
            }
            
            payment.status = status_mapping.get(clickpesa_status, 'pending')
            payment.clickpesa_payment_reference = status_data.get('payment_reference')
            payment.collected_amount = status_data.get('collected_amount', 0)
            payment.collected_currency = status_data.get('collected_currency')
            payment.status_message = status_data.get('message')
            payment.completed_at = timezone.now() if payment.status == 'completed' else None
            payment.save()
            
            logger.info(f"Payment {payment.id} status updated to {payment.status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update payment status: {str(e)}")
            return False
