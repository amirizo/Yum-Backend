# Order Workflow API Test Examples

## Test the complete order workflow

### Prerequisites
1. Have vendor, driver, and customer JWT tokens
2. Have an existing paid order in 'confirmed' status

### 1. Vendor Workflow Testing

#### Test: Set Order to Preparing
```bash
curl -X POST "http://localhost:8000/api/orders/{ORDER_UUID}/preparing/" \
  -H "Authorization: Bearer VENDOR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK)**:
```json
{
    "message": "Order status updated to preparing",
    "order_number": "ABC12345",
    "status": "preparing"
}
```

#### Test: Set Order to Ready
```bash
curl -X POST "http://localhost:8000/api/orders/{ORDER_UUID}/ready/" \
  -H "Authorization: Bearer VENDOR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK)**:
```json
{
    "message": "Order is ready for pickup. Drivers have been notified.",
    "order_number": "ABC12345",
    "status": "ready",
    "estimated_delivery": "2025-08-19T15:30:00Z"
}
```

### 2. Driver Workflow Testing

#### Test: Get Available Orders
```bash
curl -X GET "http://localhost:8000/api/orders/available-for-drivers/" \
  -H "Authorization: Bearer DRIVER_JWT_TOKEN"
```

**Expected Response (200 OK)**:
```json
{
    "available_orders": [
        {
            "id": "order-uuid",
            "order_number": "ABC12345",
            "vendor_name": "Test Restaurant",
            "vendor_address": "123 Test St",
            "customer_address": "456 Customer Ave",
            "total_amount": 25000.00,
            "item_count": 3,
            "estimated_delivery_time": "2025-08-19T15:30:00Z",
            "created_at": "2025-08-19T14:00:00Z"
        }
    ],
    "count": 1
}
```

#### Test: Assign Driver to Order
```bash
curl -X POST "http://localhost:8000/api/orders/{ORDER_UUID}/assign-driver/" \
  -H "Authorization: Bearer DRIVER_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK)**:
```json
{
    "message": "Order assigned successfully",
    "order_number": "ABC12345",
    "status": "picked_up"
}
```

#### Test: Update Driver Location
```bash
curl -X POST "http://localhost:8000/api/orders/{ORDER_UUID}/update-location/" \
  -H "Authorization: Bearer DRIVER_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": -6.7924,
    "longitude": 39.2083
  }'
```

**Expected Response (200 OK)**:
```json
{
    "message": "Location updated successfully",
    "order_status": "in_transit",
    "latitude": -6.7924,
    "longitude": 39.2083
}
```

#### Test: Mark Order as Delivered
```bash
curl -X POST "http://localhost:8000/api/orders/{ORDER_UUID}/delivered/" \
  -H "Authorization: Bearer DRIVER_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK)**:
```json
{
    "message": "Order marked as delivered successfully",
    "order_number": "ABC12345",
    "status": "delivered",
    "delivery_time": "2025-08-19T15:45:00Z"
}
```

### 3. Error Testing

#### Test: Wrong User Type
```bash
# Try to set preparing with customer token
curl -X POST "http://localhost:8000/api/orders/{ORDER_UUID}/preparing/" \
  -H "Authorization: Bearer CUSTOMER_JWT_TOKEN"
```

**Expected Response (403 Forbidden)**:
```json
{
    "error": "Only vendors can update order status"
}
```

#### Test: Invalid Order Status
```bash
# Try to set preparing on delivered order
curl -X POST "http://localhost:8000/api/orders/{DELIVERED_ORDER_UUID}/preparing/" \
  -H "Authorization: Bearer VENDOR_JWT_TOKEN"
```

**Expected Response (404 Not Found)**:
```json
{
    "error": "Order not found or cannot be updated"
}
```

### 4. Notification Testing

After running the workflow APIs, check:

#### Email Notifications Should Be Sent:
1. **Customer**: Status update emails for each transition
2. **Drivers**: New order notification when status changes to 'ready'
3. **Customer**: Thank you email when order is delivered
4. **Vendor**: Delivery confirmation when order is delivered

#### SMS Notifications Should Be Sent:
1. **Drivers**: SMS alert when new order is ready
2. **Customer**: SMS confirmation when order is delivered

### 5. Database Verification

Check that OrderStatusHistory records are created:

```python
# In Django shell
from orders.models import Order, OrderStatusHistory

order = Order.objects.get(order_number="ABC12345")
history = OrderStatusHistory.objects.filter(order=order).order_by('timestamp')

for h in history:
    print(f"{h.timestamp}: {h.status} - {h.notes}")
```

Expected output:
```
2025-08-19 14:00:00: confirmed - Order accepted by vendor
2025-08-19 14:15:00: preparing - Vendor started preparing the order
2025-08-19 14:45:00: ready - Order is ready for pickup
2025-08-19 15:00:00: picked_up - Order picked up by driver
2025-08-19 15:05:00: in_transit - Driver is en route to delivery location
2025-08-19 15:30:00: delivered - Order delivered to customer
```

### 6. Integration Testing Script

Create a Python script to test the complete workflow:

```python
import requests
import time

BASE_URL = "http://localhost:8000/api/orders"

def test_complete_workflow(order_id, vendor_token, driver_token):
    headers_vendor = {"Authorization": f"Bearer {vendor_token}"}
    headers_driver = {"Authorization": f"Bearer {driver_token}"}
    
    # 1. Vendor sets preparing
    response = requests.post(f"{BASE_URL}/{order_id}/preparing/", headers=headers_vendor)
    print(f"Set Preparing: {response.status_code} - {response.json()}")
    time.sleep(2)
    
    # 2. Vendor sets ready
    response = requests.post(f"{BASE_URL}/{order_id}/ready/", headers=headers_vendor)
    print(f"Set Ready: {response.status_code} - {response.json()}")
    time.sleep(2)
    
    # 3. Driver checks available orders
    response = requests.get(f"{BASE_URL}/available-for-drivers/", headers=headers_driver)
    print(f"Available Orders: {response.status_code} - {len(response.json()['available_orders'])} orders")
    time.sleep(2)
    
    # 4. Driver assigns themselves
    response = requests.post(f"{BASE_URL}/{order_id}/assign-driver/", headers=headers_driver)
    print(f"Assign Driver: {response.status_code} - {response.json()}")
    time.sleep(2)
    
    # 5. Driver updates location
    location_data = {"latitude": -6.7924, "longitude": 39.2083}
    response = requests.post(f"{BASE_URL}/{order_id}/update-location/", 
                           headers=headers_driver, json=location_data)
    print(f"Update Location: {response.status_code} - {response.json()}")
    time.sleep(2)
    
    # 6. Driver marks delivered
    response = requests.post(f"{BASE_URL}/{order_id}/delivered/", headers=headers_driver)
    print(f"Mark Delivered: {response.status_code} - {response.json()}")

# Usage:
# test_complete_workflow("order-uuid", "vendor-jwt", "driver-jwt")
```

This comprehensive testing approach ensures all APIs work correctly and notifications are sent properly.
