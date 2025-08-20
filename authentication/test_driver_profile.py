from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from authentication.models import Driver
import json

User = get_user_model()

class DriverProfileAPITest(APITestCase):
    """Test case for driver profile API endpoints"""
    
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
        
        # Create a customer user for permission testing
        self.customer_user = User.objects.create_user(
            email='testcustomer@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Customer',
            user_type='customer',
            phone_number='+255987654321'
        )
        
        # Profile data for testing
        self.profile_data = {
            'license_number': 'DL123456',
            'vehicle_type': 'bike',
            'vehicle_number': 'MC123',
            'vehicle_model': 'Honda CB150'
        }
    
    def get_auth_token(self, user):
        """Helper method to get authentication token"""
        response = self.client.post('/api/auth/login', {
            'email': user.email,
            'password': 'testpass123'
        })
        return response.data['access']
    
    def test_get_profile_no_profile_exists(self):
        """Test getting profile when no profile exists"""
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/auth/driver/profile')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Check for any error message in the response
        self.assertTrue('error' in response.data or 'detail' in response.data or 'message' in response.data)
    
    def test_create_driver_profile(self):
        """Test creating a driver profile"""
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post('/api/auth/driver/profile/create', self.profile_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['license_number'], self.profile_data['license_number'])
        self.assertEqual(response.data['vehicle_type'], self.profile_data['vehicle_type'])
        
        # Verify profile was created in database
        self.assertTrue(Driver.objects.filter(user=self.driver_user).exists())
    
    def test_get_profile_after_creation(self):
        """Test getting profile after it's created"""
        # First create profile
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        self.client.post('/api/auth/driver/profile/create', self.profile_data)
        
        # Then get it
        response = self.client.get('/api/auth/driver/profile')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['license_number'], self.profile_data['license_number'])
        # Profile endpoint returns basic driver info, not statistics
    
    def test_update_driver_profile(self):
        """Test updating driver profile"""
        # Create profile first
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        self.client.post('/api/auth/driver/profile/create', self.profile_data)
        
        # Update profile
        update_data = {'vehicle_model': 'Honda CB150R Updated'}
        response = self.client.patch('/api/auth/driver/profile', update_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['vehicle_model'], 'Honda CB150R Updated')
    
    def test_driver_dashboard(self):
        """Test driver dashboard endpoint"""
        # Create profile first
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        self.client.post('/api/auth/driver/profile/create', self.profile_data)
        
        # Get dashboard
        response = self.client.get('/api/auth/driver/dashboard')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
        self.assertIn('status', response.data)
        self.assertIn('driver_info', response.data)
    
    def test_toggle_availability(self):
        """Test toggling driver availability"""
        # Create profile first
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        self.client.post('/api/auth/driver/profile/create', self.profile_data)
        
        # Toggle availability
        response = self.client.post('/api/auth/driver/toggle-availability')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('is_available', response.data)
    
    def test_toggle_online_status(self):
        """Test toggling driver online status"""
        # Create profile first
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        self.client.post('/api/auth/driver/profile/create', self.profile_data)
        
        # Toggle online status
        response = self.client.post('/api/auth/driver/toggle-online')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('is_online', response.data)
    
    def test_create_duplicate_profile(self):
        """Test that creating duplicate profile fails"""
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create first profile
        self.client.post('/api/auth/driver/profile/create', self.profile_data)
        
        # Try to create another profile
        response = self.client.post('/api/auth/driver/profile/create', self.profile_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_non_driver_access_denied(self):
        """Test that non-driver users cannot access driver endpoints"""
        token = self.get_auth_token(self.customer_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/auth/driver/profile')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access driver endpoints"""
        response = self.client.get('/api/auth/driver/profile')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_invalid_vehicle_type(self):
        """Test creating profile with invalid vehicle type"""
        token = self.get_auth_token(self.driver_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        invalid_data = self.profile_data.copy()
        invalid_data['vehicle_type'] = 'invalid_type'
        
        response = self.client.post('/api/auth/driver/profile/create', invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
