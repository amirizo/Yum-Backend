# Enhanced Notification System Documentation

## Overview

The Yum Backend notification system has been completely enhanced to provide comprehensive, real-time notifications for all order status changes. The system now automatically sends notifications through multiple channels (WebSocket, email, SMS, push notifications) whenever an order status changes.

## Key Features

### ✅ **Automatic Status Notifications**
- **All order status changes** trigger notifications automatically
- **Multiple recipients**: Customers, vendors, and drivers receive relevant notifications
- **Real-time updates**: WebSocket notifications for instant updates
- **Email notifications**: Detailed email updates for important status changes
- **Driver broadcasting**: All available drivers notified when orders are ready

### ✅ **Comprehensive Status Coverage**
- `pending` → `confirmed` → `preparing` → `ready` → `picked_up` → `in_transit` → `delivered`
- Each status transition sends targeted notifications to relevant parties
- Special handling for cancelled orders

### ✅ **Multi-Channel Delivery**
- **WebSocket**: Real-time browser/app notifications
- **Email**: Detailed status updates via email
- **SMS**: Critical alerts via SMS (configurable)
- **Push Notifications**: Mobile app notifications

## Notification Types

### Order Status Notifications

| Status | Customer Notification | Vendor Notification | Driver Notification |
|--------|----------------------|-------------------|-------------------|
| **pending** | "Order created and pending confirmation" | "New order received from [customer]" | - |
| **confirmed** | "Order confirmed by [vendor]" | "Order confirmed and ready to prepare" | - |
| **preparing** | "Order being prepared by [vendor]" | "Order preparation started" | - |
| **ready** | "Order ready! Looking for driver" | "Order ready for pickup" | "New order available for pickup!" |
| **picked_up** | "Order picked up by [driver]" | "Order picked up by driver" | "Order assignment confirmed" |
| **in_transit** | "Order on the way! Track your driver" | "Order being delivered" | - |
| **delivered** | "Order delivered! Rate your experience" | "Order successfully delivered" | "Order delivery completed" |
| **cancelled** | "Order cancelled. Refund processing" | "Order has been cancelled" | - |

### Real-Time Updates

- **Location Updates**: Real-time driver location shared with customers
- **Status Updates**: Instant status changes broadcast to all relevant parties
- **ETA Updates**: Dynamic delivery time estimates

## Technical Implementation

### 1. Signal-Based Architecture

The system uses Django signals to automatically trigger notifications:

```python
# Automatic notification on order status change
@receiver(pre_save, sender=Order)
def handle_order_status_change(sender, instance, **kwargs):
    if instance.pk and old_status != instance.status:
        NotificationService.send_order_status_notification(instance, old_status)
```

### 2. Comprehensive Notification Service

```python
# Enhanced NotificationService with status-specific messaging
class NotificationService:
    @staticmethod
    def send_order_status_notification(order, old_status=None):
        # Sends appropriate notifications to all relevant parties
        # Handles WebSocket broadcasting
        # Manages email/SMS delivery
```

### 3. WebSocket Real-Time Updates

```javascript
// Example WebSocket message for order status update
{
    "type": "order_status_update",
    "data": {
        "order_id": "uuid",
        "order_number": "ABC12345",
        "status": "preparing",
        "old_status": "confirmed",
        "vendor_name": "Restaurant Name",
        "estimated_delivery_time": "2025-08-19T15:30:00Z"
    }
}
```

## API Integration

### Order Workflow APIs (Automatic Notifications)

When using these APIs, notifications are sent automatically:

```bash
# Vendor sets order to preparing
POST /api/orders/{uuid}/preparing/
# → Triggers notifications to customer and vendor

# Vendor sets order to ready
POST /api/orders/{uuid}/ready/
# → Triggers notifications to customer, vendor, and ALL available drivers

# Driver assigns themselves to order
POST /api/orders/{uuid}/assign-driver/
# → Triggers notifications to customer, vendor, and assigned driver

# Driver updates location
POST /api/orders/{uuid}/update-location/
# → Triggers real-time location updates to customer

# Driver marks delivered
POST /api/orders/{uuid}/delivered/
# → Triggers delivery confirmation to customer and vendor
```

## Notification Preferences

Users can control which notifications they receive:

```python
class NotificationPreference(models.Model):
    # Channel preferences
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    websocket_enabled = models.BooleanField(default=True)
    
    # Notification type preferences
    order_updates = models.BooleanField(default=True)
    delivery_updates = models.BooleanField(default=True)
    payment_updates = models.BooleanField(default=True)
    promotional = models.BooleanField(default=False)
    system_alerts = models.BooleanField(default=True)
```

## WebSocket Connection

### For Customers/Vendors/Drivers
```javascript
const socket = new WebSocket('ws://localhost:8000/ws/notifications/');

socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'order_status_update':
            // Handle order status change
            break;
        case 'new_order_available':
            // Handle new order notification (drivers)
            break;
        case 'driver_location_update':
            // Handle real-time location updates
            break;
        case 'notification':
            // Handle general notifications
            break;
    }
};
```

### For Order Tracking
```javascript
const trackingSocket = new WebSocket(`ws://localhost:8000/ws/tracking/${orderId}/`);

trackingSocket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'tracking_update') {
        // Update map with driver location
        updateDriverLocation(data.data.latitude, data.data.longitude);
    }
};
```

## Database Schema Updates

### New Notification Types
```python
NOTIFICATION_TYPES = [
    ('order_created', 'Order Created'),
    ('order_confirmed', 'Order Confirmed'),
    ('order_preparing', 'Order Being Prepared'),        # NEW
    ('order_ready', 'Order Ready for Pickup'),          # NEW
    ('order_available', 'Order Available for Drivers'), # NEW
    ('order_assigned', 'Order Assigned'),
    ('driver_en_route', 'Driver En Route'),
    ('driver_arrived', 'Driver Arrived'),
    ('order_picked_up', 'Order Picked Up'),
    ('order_in_transit', 'Order In Transit'),
    ('order_delivered', 'Order Delivered'),
    ('order_cancelled', 'Order Cancelled'),
    ('location_update', 'Location Update'),             # NEW
    ('status_update', 'Status Update'),                 # NEW
    # ... other types
]
```

## Testing the Enhanced System

### 1. Order Creation Test
```bash
# Create a new order
POST /api/payments/create-order-and-payment/
# Expected: Customer and vendor receive "order created" notifications
```

### 2. Status Transition Test
```bash
# Vendor confirms order
POST /api/orders/{uuid}/preparing/
# Expected: Customer receives "order being prepared" notification

# Vendor sets ready
POST /api/orders/{uuid}/ready/
# Expected: Customer receives "order ready" + ALL drivers receive "new order available"
```

### 3. Real-Time Location Test
```bash
# Driver updates location
POST /api/orders/{uuid}/update-location/
# Expected: Customer receives real-time location updates via WebSocket
```

## Error Handling

The notification system includes comprehensive error handling:

- **Failed email delivery**: Logged but doesn't break order workflow
- **WebSocket disconnections**: Gracefully handled with reconnection
- **Invalid user preferences**: Default preferences created automatically
- **Missing driver/vendor profiles**: Safely skipped with logging

## Performance Considerations

- **Async WebSocket delivery**: Non-blocking real-time updates
- **Batched email sending**: Efficient email delivery
- **Database indexing**: Optimized notification queries
- **Connection pooling**: Efficient WebSocket connections

## Monitoring & Logging

All notification activities are logged:

```python
logger.info(f"Order {order.order_number} status changed from {old_status} to {new_status}")
logger.error(f"Error sending notification: {str(e)}")
```

## Migration Applied

The notification system enhancement has been deployed with:

```bash
python manage.py makemigrations notifications
python manage.py migrate notifications
```

## Summary

The enhanced notification system provides:

✅ **100% status coverage** - Every status change triggers appropriate notifications  
✅ **Multi-stakeholder notifications** - Customers, vendors, and drivers all informed  
✅ **Real-time updates** - WebSocket integration for instant notifications  
✅ **Automatic driver alerts** - All available drivers notified when orders are ready  
✅ **Location tracking** - Real-time driver location updates  
✅ **User preferences** - Customizable notification settings  
✅ **Error resilience** - Robust error handling and logging  
✅ **Performance optimized** - Efficient delivery mechanisms  

Your Yum Backend now has a enterprise-grade notification system that ensures all stakeholders are informed at every step of the order journey! 🚀
