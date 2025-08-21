from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class AccountDeletionAPITestCase(APITestCase):
    def setUp(self):
        # Create test users
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            user_type='customer'
        )
        
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True,
            is_superuser=True
        )
        
        # Create tokens
        self.user_token = Token.objects.create(user=self.user)
        self.admin_token = Token.objects.create(user=self.admin_user)

    def test_soft_delete_account(self):
        """Test soft deleting user account"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.user_token.key)
        
        data = {
            'reason': 'No longer need the service',
            'confirm_deletion': True
        }
        
        response = self.client.post('/api/auth/account/soft-delete', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh user from database
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_deleted)
        self.assertIsNotNone(self.user.deleted_at)
        self.assertFalse(self.user.is_active)

    def test_soft_delete_without_confirmation(self):
        """Test soft delete fails without confirmation"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.user_token.key)
        
        data = {
            'reason': 'Test reason',
            'confirm_deletion': False
        }
        
        response = self.client.post('/api/auth/account/soft-delete', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hard_delete_account(self):
        """Test permanently deleting user account"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.user_token.key)
        user_id = self.user.id
        
        data = {
            'reason': 'Want permanent deletion',
            'confirm_deletion': True
        }
        
        response = self.client.delete('/api/auth/account/hard-delete', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User should no longer exist
        self.assertFalse(User.objects.filter(id=user_id).exists())

    def test_restore_soft_deleted_account(self):
        """Test restoring a soft deleted account"""
        # First soft delete the account
        self.user.soft_delete(reason='Test deletion')
        
        data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        
        response = self.client.post('/api/auth/account/restore', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh user from database
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_deleted)
        self.assertIsNone(self.user.deleted_at)
        self.assertTrue(self.user.is_active)

    def test_restore_account_with_wrong_password(self):
        """Test restore fails with wrong password"""
        self.user.soft_delete(reason='Test deletion')
        
        data = {
            'email': self.user.email,
            'password': 'wrongpassword'
        }
        
        response = self.client.post('/api/auth/account/restore', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_restore_account_expired(self):
        """Test restore fails after 30 days"""
        # Set deletion date to 31 days ago
        old_date = timezone.now() - timedelta(days=31)
        self.user.is_deleted = True
        self.user.deleted_at = old_date
        self.user.save()
        
        data = {
            'email': self.user.email,
            'password': 'testpass123'
        }
        
        response = self.client.post('/api/auth/account/restore', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_deletion_status(self):
        """Test getting account deletion status"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.user_token.key)
        
        # Check status for active account
        response = self.client.get('/api/auth/account/status')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_deleted'])
        
        # Soft delete the account
        self.user.soft_delete(reason='Test')
        
        # For deleted accounts, check status using email parameter (since token might be invalid)
        self.client.credentials()  # Remove credentials
        response = self.client.get(f'/api/auth/account/status?email={self.user.email}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_deleted'])

    def test_admin_soft_delete_user(self):
        """Test admin soft deleting any user"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        
        data = {
            'user_id': self.user.id,
            'deletion_type': 'soft',
            'reason': 'Admin decision'
        }
        
        response = self.client.post('/api/auth/admin/accounts', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_deleted)

    def test_admin_hard_delete_user(self):
        """Test admin permanently deleting any user"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        user_id = self.user.id
        
        data = {
            'user_id': self.user.id,
            'deletion_type': 'hard',
            'reason': 'Admin permanent deletion'
        }
        
        response = self.client.post('/api/auth/admin/accounts', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User should no longer exist
        self.assertFalse(User.objects.filter(id=user_id).exists())

    def test_admin_list_deleted_accounts(self):
        """Test admin listing deleted accounts"""
        # Create a deleted user
        self.user.soft_delete(reason='Test deletion')
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        
        response = self.client.get('/api/auth/admin/accounts')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)

    def test_admin_restore_user(self):
        """Test admin restoring a deleted user"""
        self.user.soft_delete(reason='Test deletion')
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        
        response = self.client.post(f'/api/auth/admin/accounts/{self.user.id}/restore')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_deleted)

    def test_non_admin_cannot_access_admin_endpoints(self):
        """Test that non-admin users cannot access admin endpoints"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.user_token.key)
        
        # Try to access admin endpoints
        response = self.client.get('/api/auth/admin/accounts')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        response = self.client.post('/api/auth/admin/accounts', {
            'user_id': self.user.id,
            'deletion_type': 'soft',
            'reason': 'Test'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_delete_superuser(self):
        """Test that admin cannot delete superuser accounts"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        
        data = {
            'user_id': self.admin_user.id,  # Try to delete superuser
            'deletion_type': 'soft',
            'reason': 'Test'
        }
        
        response = self.client.post('/api/auth/admin/accounts', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
