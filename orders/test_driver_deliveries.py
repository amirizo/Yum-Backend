from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from authentication.models import Driver, Vendor
from orders.models import Order, Product, Category
from decimal import Decimal
import json

User = get_user_model()

class DriverDeliveriesAPITest(APITestCase):
    """Test case for driver deliveries API endpoint"""
    
    def setUp(self):
        """Set up test data"""
        # Create a driver user
        self.driver_user = User.objects.create_user(
            email='testdriver@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Driver',
            user_type='driver',
            phone_number='+255123456789'
        )
        
        # Create driver profile
        self.driver_profile = Driver.objects.create(
            user=self.driver_user,
            license_number='DL123456',
            vehicle_type='bike',
            vehicle_number='MC123',
            vehicle_model='Honda CB150'
        )
        
        # Create a vendor user
        self.vendor_user = User.objects.create_user(
            email='testvendor@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Vendor',
            user_type='vendor',
            phone_number='+255987654321'
        )
        
        # Create vendor profile
        self.vendor_profile = Vendor.objects.create(
            user=self.vendor_user,
            business_name='Test Restaurant',
            business_address='Test Address',
            business_phone='+255111111111'
        )
        
        # Create a customer user
        self.customer_user = User.objects.create_user(
            email='testcustomer@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Customer',
            user_type='customer',
            phone_number='+255444444444'
        )
        
        # Create test category and product
        self.category = Category.objects.create(
            name='Test Food',
            category_type='food'
        )
        
        self.product = Product.objects.create(
            name='Test Burger',
            description='Test description',
            price=Decimal('15000'),
            vendor=self.vendor_profile,
            category=self.category,
            stock_quantity=10
        )
    
    def get_auth_token(self, user):
        """Helper method to get authentication token"""
        response = self.client.post('/api/auth/login', {
            'email': user.email,
            'password': 'testpass123'
        })
        return response.data['access']
    
    def create_test_order(self, status='picked_up', order_number=None):
        """Helper method to create a test order"""
        if order_number is None:
            import random
            import string
            order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        return Order.objects.create(
            order_number=order_number,
            customer=self.customer_user,
            vendor=self.vendor_profile,
            driver=self.driver_profile,
            status=status,
            subtotal=Decimal('15000'),
            total_amount=Decimal('20000'),
            delivery_fee=Decimal('5000'),
            payment_status='paid',
            delivery_address_text='Test Delivery Address',
            delivery_latitude='-6.7924',
            delivery_longitude='39.2083'
        )
    
    def test_get_driver_deliveries_success(self):
        """Test successfully getting driver deliveries"""
        # Create test orders
        order1 = self.create_test_order(status='delivered')
        order2 = self.create_test_order(status='in_transit')
        order3 = self.create_test_order(status='picked_up')
        
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/orders/driver/deliveries/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('deliveries', response.data)
        self.assertIn('statistics', response.data)
        self.assertIn('pagination', response.data)
        self.assertEqual(len(response.data['deliveries']), 3)
    
    def test_get_driver_deliveries_with_status_filter(self):
        """Test getting driver deliveries with status filter"""
        # Create test orders
        order1 = self.create_test_order(status='delivered')
        order2 = self.create_test_order(status='in_transit')
        order3 = self.create_test_order(status='picked_up')
        
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Filter by delivered status
        response = self.client.get('/api/orders/driver/deliveries/?status=delivered')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['deliveries']), 1)
        self.assertEqual(response.data['deliveries'][0]['status'], 'delivered')
    
    def test_get_driver_deliveries_with_pagination(self):
        """Test getting driver deliveries with pagination"""
        # Create multiple test orders
        for i in range(25):
            self.create_test_order(status='delivered')
        
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Test first page
        response = self.client.get('/api/orders/driver/deliveries/?page=1&page_size=10')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['deliveries']), 10)
        self.assertEqual(response.data['pagination']['current_page'], 1)
        self.assertEqual(response.data['pagination']['total_count'], 25)
        self.assertTrue(response.data['pagination']['has_next'])
        
        # Test second page
        response = self.client.get('/api/orders/driver/deliveries/?page=2&page_size=10')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['deliveries']), 10)
        self.assertEqual(response.data['pagination']['current_page'], 2)
    
    def test_get_driver_deliveries_invalid_status(self):
        """Test getting driver deliveries with invalid status filter"""
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/orders/driver/deliveries/?status=invalid_status')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_get_driver_deliveries_non_driver_access_denied(self):
        """Test that non-driver users cannot access the endpoint"""
        token = self.get_auth_token(self.customer_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/orders/driver/deliveries/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.data)
    
    def test_get_driver_deliveries_unauthenticated(self):
        """Test that unauthenticated users cannot access the endpoint"""
        response = self.client.get('/api/orders/driver/deliveries/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_driver_deliveries_empty_list(self):
        """Test getting driver deliveries when no orders exist"""
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/orders/driver/deliveries/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['deliveries']), 0)
        self.assertEqual(response.data['statistics']['total_deliveries'], 0)
    
    def test_get_driver_deliveries_statistics(self):
        """Test that statistics are calculated correctly"""
        # Create test orders
        self.create_test_order(status='delivered')
        self.create_test_order(status='delivered')
        self.create_test_order(status='in_transit')
        
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/orders/driver/deliveries/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stats = response.data['statistics']
        self.assertEqual(stats['total_deliveries'], 2)
        self.assertEqual(stats['active_deliveries'], 1)
        self.assertGreater(stats['completion_rate'], 0)
    
    def test_delivery_data_structure(self):
        """Test that delivery data has the correct structure"""
        order = self.create_test_order(status='delivered')
        
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/orders/driver/deliveries/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        delivery = response.data['deliveries'][0]
        
        # Check required fields
        required_fields = [
            'id', 'order_number', 'status', 'customer_info',
            'vendor_info', 'addresses', 'order_details', 'earnings',
            'timestamps', 'payment_status'
        ]
        
        for field in required_fields:
            self.assertIn(field, delivery)
        
        # Check nested structures
        self.assertIn('name', delivery['customer_info'])
        self.assertIn('phone', delivery['customer_info'])
        self.assertIn('pickup_address', delivery['addresses'])
        self.assertIn('delivery_address', delivery['addresses'])
        self.assertIn('total_amount', delivery['order_details'])
        self.assertIn('delivery_earnings', delivery['earnings'])
