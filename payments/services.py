import requests
import json
import hashlib
import logging
import uuid
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
            headers = { **self._auth_header(token), "Content-Type": "application/json" }
            
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
        
        headers = { **self._auth_header(token), "Content-Type": "application/json" }
        
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
        
        headers = { **self._auth_header(token), "Content-Type": "application/json" }
        
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


    #cards payments
    def create_card_payment(self, amount, order_reference, customer_name, customer_email, customer_phone):
        """Create card payment (normalized return). Returns dict with 'success' key.
        Uses a valid customer id (phone number if available, else email, else generated uuid).
        Attempts to create remote customer on provider if required.
        """
        token = self.generate_token()
        if not token:
            return {'success': False, 'error': 'Failed to generate auth token'}

        # Use phone number as customer id when possible, otherwise email, otherwise a uuid
        if customer_phone:
            try:
                customer_id = ''.join(filter(str.isdigit, str(customer_phone))) or str(uuid.uuid4())
            except Exception:
                customer_id = str(uuid.uuid4())
        elif customer_email:
            customer_id = customer_email
        else:
            customer_id = str(uuid.uuid4())

        # Ensure remote customer exists (best-effort)
        remote_customer_id = self.ensure_remote_customer(customer_id, full_name=customer_name, email=customer_email, phone_number=customer_phone)
        if remote_customer_id is None:
            # proceed but warn — provider may reject if customer must exist
            logger.warning('Proceeding to create card payment without confirmed remote customer id')
            remote_customer_id = customer_id

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
        headers = { **self._auth_header(token), "Content-Type": "application/json" }

        try:
            preview_response = requests.post(preview_url, json=preview_data, headers=headers, timeout=30)
            preview_response.raise_for_status()

            # Initiate payment
            initiate_data = {
                "amount": str(round(usd_amount, 2)),
                "orderReference": order_reference,
                "currency": "USD",
                "customer": {
                    "id": str(remote_customer_id),
                    "fullName": customer_name,
                    "email": customer_email,
                    "phoneNumber": customer_phone,
                },
            }
            initiate_data["checksum"] = self.generate_checksum(initiate_data)

            initiate_url = f"{self.base_url}/payments/initiate-card-payment"
            initiate_response = requests.post(initiate_url, json=initiate_data, headers=headers, timeout=30)
            initiate_response.raise_for_status()

            result = initiate_response.json()
            logger.info(f"Card payment initiated: {result}")

            # Normalize response
            payment_link = None
            payment_reference = None
            if isinstance(result, dict):
                # common keys
                payment_link = result.get('payment_link') or result.get('paymentLink') or result.get('paymentUrl') or result.get('payment_url')
                payment_reference = result.get('paymentReference') or result.get('payment_reference') or result.get('id') or result.get('reference')
                # check nested data
                data_field = result.get('data') if isinstance(result.get('data'), dict) else None
                if not payment_link and data_field:
                    payment_link = data_field.get('payment_link') or data_field.get('paymentLink') or data_field.get('paymentUrl') or data_field.get('payment_url')
                if not payment_reference and data_field:
                    payment_reference = data_field.get('paymentReference') or data_field.get('payment_reference') or data_field.get('id') or data_field.get('reference')

            return {
                'success': True,
                'data': result,
                'payment_link': payment_link,
                'payment_reference': payment_reference
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"ClickPesa card payment error: {str(e)}")
            err_text = str(e)
            if hasattr(e, 'response') and getattr(e, 'response') is not None:
                try:
                    # Try to extract JSON message
                    err_json = e.response.json()
                    if isinstance(err_json, dict):
                        err_text = err_json.get('message') or err_json.get('error') or json.dumps(err_json)
                    else:
                        err_text = e.response.text
                except Exception:
                    try:
                        err_text = e.response.text
                    except Exception:
                        pass
            return {'success': False, 'error': err_text}
        except Exception as e:
            logger.error(f"ClickPesa card payment unexpected error: {str(e)}")
            return {'success': False, 'error': str(e)}

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
        
        headers = { **self._auth_header(token), "Content-Type": "application/json" }
        
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
        
        headers = { **self._auth_header(token), "Content-Type": "application/json" }
        
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

    def check_payment_status(self, order_reference):
        """Check payment status"""
        token = self.generate_token()
        if not token:
            return {'success': False, 'error': 'Failed to generate authorization token'}
        
        url = f"{self.base_url}/payments/{order_reference}"
        headers = { **self._auth_header(token) }
        
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

    def ensure_remote_customer(self, customer_id, full_name=None, email=None, phone_number=None, user_id=None):
        """Ensure a customer exists in ClickPesa. Attempts to create the customer if not found.
        Sends payload with userId, firstName, lastName, email and phoneNumber to provider endpoint(s).
        Returns the customer id expected by ClickPesa or None on failure.
        """
        try:
            token = self.generate_token()
            if not token:
                logger.error('No auth token available to create customer')
                return None

            # derive first/last from full_name if provided
            first_name = None
            last_name = None
            if full_name:
                parts = full_name.strip().split()
                first_name = parts[0]
                last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

            # Candidate endpoints: try provider's third-parties path first
            candidate_urls = [
                f"{self.base_url}/third-parties/customers",
                f"{self.base_url}/customers",
            ]

            payload = {
                'id': str(customer_id),
                'userId': str(user_id or customer_id),
                'firstName': first_name,
                'lastName': last_name,
                'email': email,
                'phoneNumber': phone_number
            }

            headers = { **self._auth_header(token), 'Content-Type': 'application/json' }

            for url in candidate_urls:
                try:
                    resp = requests.post(url, json=payload, headers=headers, timeout=20)
                    # treat any 2xx as success
                    if 200 <= resp.status_code < 300:
                        try:
                            data = resp.json()
                        except Exception:
                            data = {}
                        remote_id = data.get('id') or data.get('customerId') or data.get('reference')
                        if remote_id:
                            logger.info(f"Remote customer created/ensured at {url}: {remote_id}")
                            return remote_id
                        # if provider didn't return id, return our userId
                        logger.info(f"Customer created at {url} but no id returned; using requested id {payload['userId']}")
                        return str(payload['userId'])
                    else:
                        # log response body for diagnostics
                        text = None
                        try:
                            text = resp.json()
                        except Exception:
                            text = resp.text
                        logger.warning(f"Customer create attempt at {url} returned status {resp.status_code}: {text}")

                        # handle already exists messages
                        try:
                            err = resp.json()
                            msg = (err.get('message') or err.get('error') or '')
                            if isinstance(msg, str) and ('exists' in msg.lower() or 'already' in msg.lower() or 'found' in msg.lower()):
                                logger.info(f"Customer already exists according to {url}; using id {customer_id}")
                                return str(customer_id)
                        except Exception:
                            pass
                        # try next url
                except Exception as e:
                    logger.debug(f"Customer create attempt failed for {url}: {e}")
            logger.warning('Failed to create/ensure remote customer; provider may require pre-registered customer')
            return None
        except Exception as e:
            logger.error(f"ensure_remote_customer error: {e}")
            return None

    def _auth_header(self, token):
        """Return authorization header dict, prefixing with 'Bearer ' only if missing."""
        if not token:
            return {}
        try:
            if isinstance(token, str) and token.lower().startswith('bearer '):
                auth_value = token
            else:
                auth_value = f"Bearer {token}"
            return { 'Authorization': auth_value }
        except Exception:
            return { 'Authorization': f"Bearer {token}" }

