import requests
import json
import hashlib
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from authentication.services import SMSService

logger = logging.getLogger(__name__)

class ClickPesaService:
    def __init__(self):
        self.client_id = settings.CLICKPESA_CLIENT_ID
        self.api_key = settings.CLICKPESA_API_KEY
        self.base_url = settings.CLICKPESA_BASE_URL
        
    def generate_token(self):
        """Generate JWT token for ClickPesa API"""
        # Check cache first
        cached_token = cache.get('clickpesa_token')
        if cached_token:
            return cached_token
            
        url = f"{self.base_url}/generate-token"
        headers = {
            "client-id": self.client_id,
            "api-key": self.api_key
        }
        
        try:
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info("ClickPesa auth token generated successfully")
            
            if data.get('success') and data.get('token'):
                token = data['token']
                # Cache token for 50 minutes (expires in 1 hour)
                cache.set('clickpesa_token', token, 3000)
                return token
            else:
                logger.error(f"ClickPesa token generation failed: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa token generation error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"ClickPesa token generation unexpected error: {str(e)}")
            return None
    
    def generate_checksum(self, data):
        """Generate checksum for ClickPesa requests"""
        # Create checksum from concatenated values
        checksum_string = f"{data.get('amount', '')}{data.get('currency', '')}{data.get('orderReference', '')}"
        if 'phoneNumber' in data:
            checksum_string += data['phoneNumber']
        
        return hashlib.md5(checksum_string.encode()).hexdigest()

    

    def create_mobile_money_payment(self, amount, phone_number, order_reference, provider=None):
        """Create mobile money payment using USSD push"""
        try:
            token = self.generate_token()
            if not token:
                return {'success': False, 'error': 'Failed to generate auth token'}
            
            # Preview first to check availability
            preview_data = {
                "amount": str(amount),
                "currency": "TZS",
                "orderReference": order_reference,
                "phoneNumber": phone_number,
                "checksum": self.generate_checksum({
                    "amount": str(amount),
                    "currency": "TZS", 
                    "orderReference": order_reference,
                    "phoneNumber": phone_number
                })
            }
            
            preview_url = f"{self.base_url}/payments/preview-ussd-push-request"
            headers = {
                "Authorization": token,
                "Content-Type": "application/json"
            }
            
            preview_response = requests.post(preview_url, json=preview_data, headers=headers)
            
            if preview_response.status_code != 200:
                logger.error(f"ClickPesa preview failed: {preview_response.status_code} - {preview_response.text}")
                return {'success': False, 'error': 'Payment method not available'}
            
            preview_result = preview_response.json()
            
            # Check if any methods are available
            active_methods = preview_result.get('activeMethods', [])
            if not active_methods:
                return {'success': False, 'error': 'No payment methods available'}
            
            # Initiate payment
            initiate_url = f"{self.base_url}/payments/initiate-ussd-push-request"
            initiate_response = requests.post(initiate_url, json=preview_data, headers=headers)
            
            if initiate_response.status_code != 200:
                logger.error(f"ClickPesa initiate failed: {initiate_response.status_code} - {initiate_response.text}")
                return {'success': False, 'error': 'Failed to initiate payment'}
            
            result = initiate_response.json()
            
            return {
                'success': True,
                'payment_id': result.get('id'),
                'status': result.get('status'),
                'order_reference': result.get('orderReference'),
                'message': 'USSD push sent to customer phone'
            }
            
        except Exception as e:
            logger.error(f"Mobile money payment error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    
    def preview_mobile_money_payment(self, amount, phone_number, order_reference):
        """Preview mobile money payment to check availability"""
        token = self.generate_token()
        if not token:
            return {'success': False, 'error': 'Failed to generate authorization token'}
        
        url = f"{self.base_url}/payments/preview-ussd-push-request"
        
        payload = {
            "amount": str(amount),
            "currency": "TZS",
            "orderReference": order_reference,
            "phoneNumber": phone_number,
            "checksum": self.generate_checksum({
                "amount": str(amount),
                "currency": "TZS", 
                "orderReference": order_reference,
                "phoneNumber": phone_number
            })
        }
        
        headers = {
            "Authorization": token,  # Token already includes "Bearer "
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"ClickPesa mobile money preview successful for order {order_reference}")
            return {'success': True, 'data': data}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa preview failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"ClickPesa preview error response: {error_data}")
                except:
                    logger.error(f"ClickPesa preview error status: {e.response.status_code}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"ClickPesa preview unexpected error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def initiate_mobile_money_payment(self, amount, phone_number, order_reference):
        """Initiate mobile money payment"""
        token = self.generate_token()
        if not token:
            return {'success': False, 'error': 'Failed to generate authorization token'}
        
        url = f"{self.base_url}/payments/initiate-ussd-push-request"
        
        payload = {
            "amount": str(amount),
            "currency": "TZS",
            "orderReference": order_reference,
            "phoneNumber": phone_number,
            "checksum": self.generate_checksum({
                "amount": str(amount),
                "currency": "TZS",
                "orderReference": order_reference,
                "phoneNumber": phone_number
            })
        }
        
        headers = {
            "Authorization": token,  # Token already includes "Bearer "
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"ClickPesa mobile money payment initiated for order {order_reference}")
            return {'success': True, 'data': data}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa mobile money initiation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"ClickPesa mobile money initiation unexpected error: {str(e)}")
            return {'success': False, 'error': str(e)}



    def create_card_payment(self, amount, order_reference, customer_name, customer_email, customer_phone):
        """Create card payment"""
        token = self.generate_token()
        if not token:
            return None
            
        # Convert TZS to USD for card payments (approximate rate)
        usd_amount = float(amount) / 2300  # Approximate TZS to USD conversion
        
        # Preview first
        preview_data = {
            "amount": str(round(usd_amount, 2)),
            "currency": "USD",
            "orderReference": order_reference,
            "checksum": ""
        }
        preview_data["checksum"] = self.generate_checksum(preview_data)
        
        preview_url = f"{self.base_url}/payments/preview-card-payment"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        
        try:
            preview_response = requests.post(preview_url, json=preview_data, headers=headers)
            preview_response.raise_for_status()
            
            # Initiate payment
            initiate_data = {
                "amount": str(round(usd_amount, 2)),
                "orderReference": order_reference,
                "currency": "USD",
                "customer": {
                    "id": str(hash(customer_name)),
                    "fullName": customer_name,
                    "email": customer_email,
                    "phoneNumber": customer_phone,
                },       
                
            }
            initiate_data["checksum"] = self.generate_checksum(initiate_data)
            
            initiate_url = f"{self.base_url}/payments/initiate-card-payment"
            initiate_response = requests.post(initiate_url, json=initiate_data, headers=headers)
            initiate_response.raise_for_status()
            
            result = initiate_response.json()
            logger.info(f"Card payment initiated: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa card payment error: {str(e)}")
            return None

    def preview_card_payment(self, amount, order_reference):
        """Preview card payment"""
        token = self.generate_token()
        if not token:
            return {'success': False, 'error': 'Failed to generate authorization token'}
        
        url = f"{self.base_url}/payments/preview-card-payment"
        
        payload = {
            "amount": str(amount),
            "currency": "USD",
            "orderReference": order_reference,
            "checksum": self.generate_checksum({
                "amount": str(amount),
                "currency": "USD",
                "orderReference": order_reference
            })
        }
        
        headers = {
            "Authorization": token,  # Token already includes "Bearer "
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"ClickPesa card payment preview successful for order {order_reference}")
            return {'success': True, 'data': data}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa card preview failed: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"ClickPesa card preview unexpected error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def initiate_card_payment(self, amount, order_reference, customer_id):
        """Initiate card payment"""
        token = self.generate_token()
        if not token:
            return {'success': False, 'error': 'Failed to generate authorization token'}
        
        url = f"{self.base_url}/payments/initiate-card-payment"
        
        payload = {
            "amount": str(amount),
            "currency": "USD",
            "orderReference": order_reference,
            "customer": {"id": str(customer_id)},
            "checksum": self.generate_checksum({
                "amount": str(amount),
                "currency": "USD",
                "orderReference": order_reference
            })
        }
        
        headers = {
            "Authorization": token,  # Token already includes "Bearer "
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"ClickPesa card payment initiated for order {order_reference}")
            return {'success': True, 'data': data}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa card payment initiation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"ClickPesa card payment initiation unexpected error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def create_mobile_money_payment(self, amount, phone_number, order_reference):
        """Create mobile money payment using USSD push"""
        token = self.generate_token()
        if not token:
            return None
            
        # Preview first
        preview_data = {
            "amount": str(amount),
            "currency": "TZS",
            "orderReference": order_reference,
            "phoneNumber": phone_number,
            "checksum": ""
        }
        preview_data["checksum"] = self.generate_checksum(preview_data)
        
        preview_url = f"{self.base_url}/payments/preview-ussd-push-request"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        
        try:
            preview_response = requests.post(preview_url, json=preview_data, headers=headers)
            preview_response.raise_for_status()
            
            # Initiate payment
            initiate_data = {
                "amount": str(amount),
                "currency": "TZS",
                "orderReference": order_reference,
                "phoneNumber": phone_number,
                "checksum": ""
            }
            initiate_data["checksum"] = self.generate_checksum(initiate_data)
            
            initiate_url = f"{self.base_url}/payments/initiate-ussd-push-request"
            initiate_response = requests.post(initiate_url, json=initiate_data, headers=headers)
            initiate_response.raise_for_status()
            
            result = initiate_response.json()
            logger.info(f"Mobile money payment initiated: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa mobile money payment error: {str(e)}")
            return None
    
    def check_payment_status(self, order_reference):
        """Check payment status"""
        token = self.generate_token()
        if not token:
            return {'success': False, 'error': 'Failed to generate authorization token'}
        
        url = f"{self.base_url}/payments/{order_reference}"
        headers = {
            "Authorization": token  # Token already includes "Bearer "
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"ClickPesa payment status checked for order {order_reference}")
            return {'success': True, 'data': data}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa payment status check failed: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"ClickPesa payment status check unexpected error: {str(e)}")
            return {'success': False, 'error': str(e)}

