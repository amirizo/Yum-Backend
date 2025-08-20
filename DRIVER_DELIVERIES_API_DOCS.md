# Driver Deliveries API Documentation

## Endpoint
`GET /api/orders/driver/deliveries/`

## Description
Retrieves all deliveries for the authenticated driver with comprehensive filtering, pagination, and statistics.

## Authentication
- **Required**: Yes
- **Type**: JWT Bearer Token
- **User Type**: Driver only

## Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `status` | string | No | Filter by order status | `delivered`, `in_transit`, `picked_up`, `cancelled` |
| `date_from` | string | No | Filter orders from date (YYYY-MM-DD) | `2024-01-01` |
| `date_to` | string | No | Filter orders to date (YYYY-MM-DD) | `2024-12-31` |
| `page` | integer | No | Page number for pagination (default: 1) | `2` |
| `page_size` | integer | No | Items per page (default: 20) | `10` |

## Response Format

### Success Response (200 OK)

```json
{
    "deliveries": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "order_number": "ABC123DEF",
            "status": "delivered",
            "customer_info": {
                "name": "John Doe",
                "phone": "+255123456789",
                "email": "john@example.com"
            },
            "vendor_info": {
                "name": "Pizza Palace",
                "phone": "+255987654321"
            },
            "addresses": {
                "pickup_address": "123 Restaurant Street, Dar es Salaam",
                "delivery_address": "456 Customer Avenue, Dar es Salaam",
                "delivery_latitude": "-6.7924",
                "delivery_longitude": "39.2083"
            },
            "order_details": {
                "items": [
                    {
                        "product_name": "Margherita Pizza",
                        "quantity": 2,
                        "price": "25000.00"
                    }
                ],
                "total_amount": "30000.00",
                "delivery_fee": "5000.00",
                "item_count": 2
            },
            "earnings": {
                "delivery_earnings": "4000.00",
                "currency": "TZS"
            },
            "timestamps": {
                "ordered_at": "2024-01-15T10:30:00Z",
                "picked_up_at": "2024-01-15T11:00:00Z",
                "delivered_at": "2024-01-15T11:30:00Z",
                "estimated_delivery": "2024-01-15T11:45:00Z"
            },
            "payment_status": "paid",
            "special_instructions": "Ring doorbell twice"
        }
    ],
    "statistics": {
        "total_deliveries": 125,
        "active_deliveries": 2,
        "total_earnings": 250000.00,
        "completion_rate": 95.5
    },
    "pagination": {
        "current_page": 1,
        "page_size": 20,
        "total_count": 125,
        "total_pages": 7,
        "has_next": true,
        "has_previous": false
    },
    "filters_applied": {
        "status": null,
        "date_from": null,
        "date_to": null
    }
}
```

## Response Fields Description

### Deliveries Array
Each delivery object contains:

- **Basic Info**: Order ID, number, and current status
- **Customer Info**: Customer name, phone, and email
- **Vendor Info**: Restaurant/vendor name and contact
- **Addresses**: Pickup and delivery locations with coordinates
- **Order Details**: Items ordered, pricing, and special instructions
- **Earnings**: Driver's share of delivery fee (typically 80% of delivery fee)
- **Timestamps**: Key milestone timestamps for order tracking
- **Payment Status**: Current payment status of the order

### Statistics Object
- **total_deliveries**: Total completed deliveries by this driver
- **active_deliveries**: Current orders in progress (picked_up, in_transit)
- **total_earnings**: Total earnings from deliveries (driver's share)
- **completion_rate**: Percentage of assigned orders completed successfully

### Pagination Object
Standard pagination information including current page, total pages, and navigation flags.

## Example Requests

### Get All Deliveries
```bash
GET /api/orders/driver/deliveries/
Authorization: Bearer <jwt_token>
```

### Filter by Status
```bash
GET /api/orders/driver/deliveries/?status=delivered
Authorization: Bearer <jwt_token>
```

### Filter by Date Range
```bash
GET /api/orders/driver/deliveries/?date_from=2024-01-01&date_to=2024-01-31
Authorization: Bearer <jwt_token>
```

### Pagination
```bash
GET /api/orders/driver/deliveries/?page=2&page_size=10
Authorization: Bearer <jwt_token>
```

### Combined Filters
```bash
GET /api/orders/driver/deliveries/?status=delivered&date_from=2024-01-01&page=1&page_size=15
Authorization: Bearer <jwt_token>
```

## Error Responses

### 401 Unauthorized
```json
{
    "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
    "error": "Only drivers can access this endpoint"
}
```

### 400 Bad Request (Invalid Status)
```json
{
    "error": "Invalid status. Valid options: picked_up, in_transit, delivered, cancelled"
}
```

### 400 Bad Request (Invalid Date Format)
```json
{
    "error": "Invalid date_from format. Use YYYY-MM-DD"
}
```

### 500 Internal Server Error
```json
{
    "error": "An error occurred while retrieving deliveries"
}
```

## Valid Status Values
- `picked_up`: Order has been picked up from vendor
- `in_transit`: Driver is on the way to delivery location
- `delivered`: Order has been successfully delivered
- `cancelled`: Order was cancelled

## Notes

1. **Earnings Calculation**: Driver earnings are calculated as 80% of the delivery fee. This can be adjusted in the backend configuration.

2. **Date Filtering**: Date filters apply to the order creation date (`created_at` field).

3. **Pagination**: Default page size is 20 items. Maximum recommended page size is 100.

4. **Ordering**: Results are ordered by creation date (newest first) unless filtered by distance.

5. **Distance Calculation**: If driver's current location is available, orders may be sorted by distance from the driver.

6. **Real-time Updates**: This endpoint provides current data. For real-time updates, use WebSocket connections.

## Integration Tips

1. **Mobile App**: Use this endpoint to populate the driver's delivery history screen
2. **Dashboard**: Statistics object is perfect for driver dashboard widgets
3. **Filtering**: Implement status and date filters in your UI for better user experience
4. **Pagination**: Implement infinite scroll or pagination controls using the pagination object
5. **Caching**: Consider caching responses for better performance, especially for statistics

## Related Endpoints
- `GET /api/orders/available-for-drivers/` - Get available orders for pickup
- `POST /api/orders/{order_id}/assign-driver/` - Accept an order
- `POST /api/orders/{order_id}/delivered/` - Mark order as delivered
- `POST /api/orders/{order_id}/update-location/` - Update driver location during delivery
