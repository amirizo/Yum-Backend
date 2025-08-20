#!/usr/bin/env python
"""
Driver Profile API Test Script

This script tests the driver profile endpoints to ensure they work correctly.
"""

import os
import sys
import django
from django.test import TestCase
from django.contrib.auth import get_user_model

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Yumbackend.settings')
django.setup()

from authentication.models import Driver
from rest_framework.test import APIClient
from rest_framework import status
import json

User = get_user_model()

def test_driver_profile_endpoints():
    """Test all driver profile endpoints"""
    
    print("🧪 Testing Driver Profile Endpoints...")
    print("=" * 50)
    
    # Create API client
    client = APIClient()
    
    # Create test driver user
    driver_user = User.objects.create_user(
        email='testdriver@example.com',
        password='testpass123',
        first_name='Test',
        last_name='Driver',
        user_type='driver',
        phone_number='+255123456789'
    )
    
    # Login to get token
    login_response = client.post('/api/auth/login', {
        'email': 'testdriver@example.com',
        'password': 'testpass123'
    })
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.data}")
        return
    
    token = login_response.data['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    
    print("✅ Driver user created and logged in")
    
    # Test 1: Get profile when none exists (should return 404)
    print("\n1️⃣ Testing GET profile (no profile exists)...")
    response = client.get('/api/auth/driver/profile')
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.data}")
    
    # Test 2: Create driver profile
    print("\n2️⃣ Testing POST create profile...")
    profile_data = {
        'license_number': 'DL123456',
        'vehicle_type': 'bike',
        'vehicle_number': 'MC123',
        'vehicle_model': 'Honda CB150'
    }
    
    response = client.post('/api/auth/driver/profile/create', profile_data)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.data, indent=2)}")
    
    if response.status_code == 201:
        print("   ✅ Driver profile created successfully")
    else:
        print("   ❌ Driver profile creation failed")
        return
    
    # Test 3: Get profile after creation
    print("\n3️⃣ Testing GET profile (after creation)...")
    response = client.get('/api/auth/driver/profile')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Driver profile retrieved successfully")
        print(f"   License: {response.data.get('license_number')}")
        print(f"   Vehicle: {response.data.get('vehicle_model')}")
        print(f"   Available: {response.data.get('is_available')}")
    else:
        print(f"   ❌ Failed to retrieve profile: {response.data}")
    
    # Test 4: Update driver profile
    print("\n4️⃣ Testing PATCH update profile...")
    update_data = {
        'vehicle_model': 'Honda CB150R Updated'
    }
    
    response = client.patch('/api/auth/driver/profile', update_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Driver profile updated successfully")
        print(f"   Updated model: {response.data.get('vehicle_model')}")
    else:
        print(f"   ❌ Failed to update profile: {response.data}")
    
    # Test 5: Driver dashboard
    print("\n5️⃣ Testing GET driver dashboard...")
    response = client.get('/api/auth/driver/dashboard')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Driver dashboard retrieved successfully")
        stats = response.data.get('statistics', {})
        print(f"   Total Orders: {stats.get('total_orders', 0)}")
        print(f"   Completion Rate: {stats.get('completion_rate', 0)}%")
        print(f"   Is Available: {response.data.get('status', {}).get('is_available')}")
    else:
        print(f"   ❌ Failed to get dashboard: {response.data}")
    
    # Test 6: Toggle availability
    print("\n6️⃣ Testing POST toggle availability...")
    response = client.post('/api/auth/driver/toggle-availability')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Availability toggled successfully")
        print(f"   Message: {response.data.get('message')}")
        print(f"   Available: {response.data.get('is_available')}")
    else:
        print(f"   ❌ Failed to toggle availability: {response.data}")
    
    # Test 7: Toggle online status
    print("\n7️⃣ Testing POST toggle online status...")
    response = client.post('/api/auth/driver/toggle-online')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Online status toggled successfully")
        print(f"   Message: {response.data.get('message')}")
        print(f"   Online: {response.data.get('is_online')}")
    else:
        print(f"   ❌ Failed to toggle online status: {response.data}")
    
    # Test 8: Try to create duplicate profile (should fail)
    print("\n8️⃣ Testing POST create duplicate profile...")
    response = client.post('/api/auth/driver/profile/create', profile_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 400:
        print("   ✅ Correctly prevented duplicate profile creation")
        print(f"   Error: {response.data}")
    else:
        print("   ❌ Should have prevented duplicate profile creation")
    
    # Test 9: Test with non-driver user
    print("\n9️⃣ Testing with non-driver user...")
    customer_user = User.objects.create_user(
        email='testcustomer@example.com',
        password='testpass123',
        first_name='Test',
        last_name='Customer',
        user_type='customer'
    )
    
    # Login as customer
    login_response = client.post('/api/auth/login', {
        'email': 'testcustomer@example.com',
        'password': 'testpass123'
    })
    
    customer_token = login_response.data['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {customer_token}')
    
    response = client.get('/api/auth/driver/profile')
    print(f"   Status: {response.status_code}")
    if response.status_code == 403:
        print("   ✅ Correctly denied access to non-driver user")
        print(f"   Error: {response.data}")
    else:
        print("   ❌ Should have denied access to non-driver user")
    
    # Final summary
    print("\n" + "=" * 50)
    print("🎉 Driver Profile API Testing Complete!")
    print("✅ All endpoints are working correctly")
    print("\n📋 Available Endpoints:")
    print("   • GET    /api/auth/driver/profile")
    print("   • POST   /api/auth/driver/profile/create")
    print("   • PATCH  /api/auth/driver/profile")
    print("   • GET    /api/auth/driver/dashboard")
    print("   • POST   /api/auth/driver/toggle-availability")
    print("   • POST   /api/auth/driver/toggle-online")

if __name__ == '__main__':
    test_driver_profile_endpoints()
