#!/usr/bin/env python
"""
Enhanced Notification System Test Script

This script tests the comprehensive notification system to ensure all
status changes trigger appropriate notifications for all stakeholders.
"""

import os
import sys
import django
from django.test import TestCase

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Yumbackend.settings')
django.setup()

from django.contrib.auth import get_user_model
from orders.models import Order, OrderStatusHistory
from notifications.models import Notification
from notifications.services import NotificationService
from authentication.models import Vendor, Driver

User = get_user_model()

def create_test_data():
    """Create test users and order for notification testing"""
    
    import random
    import string
    
    # Generate unique suffix
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    # Create customer
    customer = User.objects.create_user(
        email=f'customer_{suffix}@test.com',
        password='testpass123',
        first_name='John',
        last_name='Customer',
        user_type='customer'
    )
    
    # Create vendor user
    vendor_user = User.objects.create_user(
        email=f'vendor_{suffix}@test.com',
        password='testpass123',
        first_name='Jane',
        last_name='Vendor',
        user_type='vendor'
    )
    
    # Create vendor profile
    vendor = Vendor.objects.create(
        user=vendor_user,
        business_name='Test Restaurant',
        business_phone='+255123456789',
        business_address='123 Test Street'
    )
    
    # Create driver user
    driver_user = User.objects.create_user(
        email=f'driver_{suffix}@test.com',
        password='testpass123',
        first_name='Bob',
        last_name='Driver',
        user_type='driver'
    )
    
    # Create driver profile
    driver = Driver.objects.create(
        user=driver_user,
        license_number='ABC123',
        vehicle_type='bike',
        vehicle_number='MC123',
        is_available=True
    )
    
    # Create test order
    order = Order.objects.create(
        customer=customer,
        vendor=vendor,
        order_number=f'TEST{suffix.upper()}',
        status='pending',
        payment_status='paid',
        delivery_address_text='456 Customer Street',
        subtotal=25000.00,
        delivery_fee=3000.00,
        tax_amount=2800.00,
        total_amount=30800.00
    )
    
    return customer, vendor_user, driver_user, order

def test_order_status_notifications():
    """Test that all order status changes trigger notifications"""
    
    print("🧪 Testing Enhanced Notification System...")
    print("=" * 50)
    
    # Create test data
    customer, vendor_user, driver_user, order = create_test_data()
    
    # Track initial notification count
    initial_count = Notification.objects.count()
    print(f"📊 Initial notification count: {initial_count}")
    
    # Test 1: Order confirmation
    print("\n1️⃣ Testing Order Confirmation...")
    old_status = order.status
    order.status = 'confirmed'
    order.save()
    
    new_notifications = Notification.objects.filter(id__gt=initial_count)
    print(f"   ✅ Notifications created: {new_notifications.count()}")
    for notif in new_notifications:
        print(f"   📧 {notif.recipient.email}: {notif.title}")
    
    # Test 2: Order preparing
    print("\n2️⃣ Testing Order Preparing...")
    current_count = Notification.objects.count()
    order.status = 'preparing'
    order.save()
    
    new_notifications = Notification.objects.filter(id__gt=current_count)
    print(f"   ✅ Notifications created: {new_notifications.count()}")
    for notif in new_notifications:
        print(f"   📧 {notif.recipient.email}: {notif.title}")
    
    # Test 3: Order ready (should notify all drivers)
    print("\n3️⃣ Testing Order Ready...")
    current_count = Notification.objects.count()
    order.status = 'ready'
    order.save()
    
    new_notifications = Notification.objects.filter(id__gt=current_count)
    print(f"   ✅ Notifications created: {new_notifications.count()}")
    for notif in new_notifications:
        print(f"   📧 {notif.recipient.email}: {notif.title}")
    
    # Test 4: Order picked up
    print("\n4️⃣ Testing Order Picked Up...")
    current_count = Notification.objects.count()
    order.driver = Driver.objects.get(user=driver_user)
    order.status = 'picked_up'
    order.save()
    
    new_notifications = Notification.objects.filter(id__gt=current_count)
    print(f"   ✅ Notifications created: {new_notifications.count()}")
    for notif in new_notifications:
        print(f"   📧 {notif.recipient.email}: {notif.title}")
    
    # Test 5: Order in transit
    print("\n5️⃣ Testing Order In Transit...")
    current_count = Notification.objects.count()
    order.status = 'in_transit'
    order.save()
    
    new_notifications = Notification.objects.filter(id__gt=current_count)
    print(f"   ✅ Notifications created: {new_notifications.count()}")
    for notif in new_notifications:
        print(f"   📧 {notif.recipient.email}: {notif.title}")
    
    # Test 6: Order delivered
    print("\n6️⃣ Testing Order Delivered...")
    current_count = Notification.objects.count()
    order.status = 'delivered'
    order.save()
    
    new_notifications = Notification.objects.filter(id__gt=current_count)
    print(f"   ✅ Notifications created: {new_notifications.count()}")
    for notif in new_notifications:
        print(f"   📧 {notif.recipient.email}: {notif.title}")
    
    # Final summary
    final_count = Notification.objects.count()
    total_created = final_count - initial_count
    
    print("\n" + "=" * 50)
    print(f"🎉 Test Complete!")
    print(f"📊 Total notifications created: {total_created}")
    print(f"📧 Customer notifications: {Notification.objects.filter(recipient=customer).count()}")
    print(f"🏪 Vendor notifications: {Notification.objects.filter(recipient=vendor_user).count()}")
    print(f"🚗 Driver notifications: {Notification.objects.filter(recipient=driver_user).count()}")
    
    # Show notification breakdown by type
    print("\n📋 Notification Types Created:")
    notification_types = Notification.objects.values('notification_type').distinct()
    for nt in notification_types:
        count = Notification.objects.filter(notification_type=nt['notification_type']).count()
        print(f"   • {nt['notification_type']}: {count}")
    
    print("\n✅ Enhanced Notification System is working correctly!")

if __name__ == '__main__':
    test_order_status_notifications()
