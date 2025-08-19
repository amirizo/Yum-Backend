# Order Workflow API Documentation

## Overview
This document outlines the complete order workflow APIs for vendors and drivers, including status transitions, notifications, and email services.

## Order Status Flow

```
pending → confirmed → preparing → ready → picked_up → in_transit → delivered
                   ↓
               cancelled (at any point before pickup)
```

## API Endpoints

### Vendor Workflow APIs

#### 1. Accept Order
**POST** `/api/orders/{order_id}/accept/`
- **Authentication**: Required (Vendor only)
- **Description**: Vendor accepts a pending order
- **Prerequisites**: Order status must be 'pending' and payment_status 'paid'
- **Status Transition**: `pending → confirmed`
- **Notifications**: Email to customer

```json
{
    "message": "Order accepted successfully"
}
```

#### 2. Reject Order
**POST** `/api/orders/{order_id}/reject/`
- **Authentication**: Required (Vendor only)
- **Description**: Vendor rejects a pending order
- **Prerequisites**: Order status must be 'pending' and payment_status 'paid'
- **Status Transition**: `pending → cancelled`
- **Notifications**: Email to customer, admin notification, refund processing

**Request Body**:
```json
{
    "reason": "Ingredients not available"
}
```

#### 3. Set Preparing
**POST** `/api/orders/{order_id}/preparing/`
- **Authentication**: Required (Vendor only)
- **Description**: Vendor starts preparing the order
- **Prerequisites**: Order status must be 'confirmed' and payment_status 'paid'
- **Status Transition**: `confirmed → preparing`
- **Notifications**: Email status update to customer

```json
{
    "message": "Order status updated to preparing",
    "order_number": "ABC12345",
    "status": "preparing"
}
```

#### 4. Set Ready for Pickup
**POST** `/api/orders/{order_id}/ready/`
- **Authentication**: Required (Vendor only)
- **Description**: Vendor marks order as ready for pickup
- **Prerequisites**: Order status must be 'preparing' and payment_status 'paid'
- **Status Transition**: `preparing → ready`
- **Notifications**: 
  - SMS/Email to ALL available drivers
  - Email status update to customer
  - Sets estimated delivery time if not already set

```json
{
    "message": "Order is ready for pickup. Drivers have been notified.",
    "order_number": "ABC12345",
    "status": "ready",
    "estimated_delivery": "2025-08-19T15:30:00Z"
}
```

### Driver Workflow APIs

#### 5. Get Available Orders
**GET** `/api/orders/available-for-drivers/`
- **Authentication**: Required (Driver only)
- **Description**: Get list of orders ready for pickup
- **Filters**: Orders with status 'ready', no assigned driver, paid
- **Sorting**: By distance from driver (if location available) or creation time

```json
{
    "available_orders": [
        {
            "id": "uuid-here",
            "order_number": "ABC12345",
            "vendor_name": "Pizza Palace",
            "vendor_address": "123 Main St",
            "customer_address": "456 Oak Ave",
            "total_amount": 25000.00,
            "item_count": 3,
            "estimated_delivery_time": "2025-08-19T15:30:00Z",
            "created_at": "2025-08-19T14:00:00Z",
            "distance_km": 2.5
        }
    ],
    "count": 1
}
```

#### 6. Assign Driver to Order
**POST** `/api/orders/{order_id}/assign-driver/`
- **Authentication**: Required (Driver only)
- **Description**: Driver assigns themselves to an order
- **Prerequisites**: Order status 'ready', no driver assigned, driver available
- **Status Transition**: `ready → picked_up`
- **Notifications**: Email to customer about pickup

```json
{
    "message": "Order assigned successfully",
    "order_number": "ABC12345",
    "status": "picked_up"
}
```

#### 7. Update Location During Delivery
**POST** `/api/orders/{order_id}/update-location/`
- **Authentication**: Required (Driver only)
- **Description**: Driver updates their current location
- **Prerequisites**: Order assigned to driver, status 'picked_up' or 'in_transit'
- **Status Transition**: `picked_up → in_transit` (if not already)
- **Side Effects**: Updates driver's current location

**Request Body**:
```json
{
    "latitude": -6.7924,
    "longitude": 39.2083
}
```

```json
{
    "message": "Location updated successfully",
    "order_status": "in_transit",
    "latitude": -6.7924,
    "longitude": 39.2083
}
```

#### 8. Mark Order as Delivered
**POST** `/api/orders/{order_id}/delivered/`
- **Authentication**: Required (Driver only)
- **Description**: Driver marks order as delivered
- **Prerequisites**: Order assigned to driver, status 'picked_up' or 'in_transit'
- **Status Transition**: `picked_up/in_transit → delivered`
- **Notifications**: 
  - Thank you email + SMS to customer
  - Delivery confirmation email to vendor
  - Updates driver availability

```json
{
    "message": "Order marked as delivered successfully",
    "order_number": "ABC12345",
    "status": "delivered",
    "delivery_time": "2025-08-19T15:45:00Z"
}
```

## Notification System

### Email Notifications

#### Customer Notifications
1. **Order Accepted**: When vendor accepts order
2. **Status Updates**: For each status change (preparing, ready, picked_up, in_transit)
3. **Order Picked Up**: When driver picks up order
4. **Order Delivered**: Thank you email with delivery confirmation

#### Driver Notifications
1. **New Order Available**: SMS + Email when order is ready for pickup
2. **Order Details**: Complete order information for pickup decision

#### Vendor Notifications
1. **Order Delivered**: Confirmation when driver completes delivery

### SMS Notifications
- **Drivers**: Immediate SMS when new order is ready
- **Customers**: SMS for critical updates (delivered, cancelled)

## Database Schema Updates

### Order Model Enhancements
```python
class Order(models.Model):
    # ... existing fields ...
    
    # Enhanced delivery information
    delivery_address_text = models.TextField()  # For non-registered users
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    special_instructions = models.TextField(blank=True)
    
    # Nullable delivery_address for backward compatibility
    delivery_address = models.ForeignKey(DeliveryAddress, null=True, blank=True)
```

### Driver Profile Requirements
The Driver model should have these fields for optimal workflow:
```python
class Driver(models.Model):
    is_available = models.BooleanField(default=True)
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    last_location_update = models.DateTimeField(null=True)
    current_orders_count = models.IntegerField(default=0)
```

## Error Handling

### Common Error Responses

**403 Forbidden** - Wrong user type:
```json
{
    "error": "Only vendors can update order status"
}
```

**404 Not Found** - Order not found or invalid state:
```json
{
    "error": "Order not found or cannot be updated"
}
```

**400 Bad Request** - Business logic violation:
```json
{
    "error": "Driver is not available for deliveries"
}
```

## Usage Examples

### Complete Vendor Workflow
```bash
# 1. Accept order
curl -X POST /api/orders/uuid-here/accept/ \
  -H "Authorization: Bearer VENDOR_TOKEN"

# 2. Start preparing
curl -X POST /api/orders/uuid-here/preparing/ \
  -H "Authorization: Bearer VENDOR_TOKEN"

# 3. Mark ready (triggers driver notifications)
curl -X POST /api/orders/uuid-here/ready/ \
  -H "Authorization: Bearer VENDOR_TOKEN"
```

### Complete Driver Workflow
```bash
# 1. Check available orders
curl -X GET /api/orders/available-for-drivers/ \
  -H "Authorization: Bearer DRIVER_TOKEN"

# 2. Accept an order
curl -X POST /api/orders/uuid-here/assign-driver/ \
  -H "Authorization: Bearer DRIVER_TOKEN"

# 3. Update location during delivery
curl -X POST /api/orders/uuid-here/update-location/ \
  -H "Authorization: Bearer DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"latitude": -6.7924, "longitude": 39.2083}'

# 4. Mark as delivered
curl -X POST /api/orders/uuid-here/delivered/ \
  -H "Authorization: Bearer DRIVER_TOKEN"
```

## Service Integration

### Email Service Integration
All email notifications use the `authentication.services.EmailService` class:
- Order status updates
- Driver notifications
- Customer thank you emails
- Vendor delivery confirmations

### SMS Service Integration
Critical notifications use `authentication.services.SMSService`:
- Driver notifications for new orders
- Customer delivery confirmations
- Order cancellation alerts

## Real-time Features
- Driver location tracking during delivery
- Automatic status transitions with notifications
- Distance-based order assignment recommendations
- Real-time driver availability management

This workflow ensures complete order lifecycle management with proper notifications and status tracking.
