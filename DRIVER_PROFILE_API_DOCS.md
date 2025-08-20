# Driver Profile API Documentation

## Driver Profile Management Endpoints

The following endpoints have been created for comprehensive driver profile management:

### 1. **GET Driver Profile**
```
GET /api/auth/driver/profile
```
**Description**: Retrieve the authenticated driver's profile information

**Headers**:
```
Authorization: Bearer <JWT_TOKEN>
```

**Response** (200 OK):
```json
{
    "id": 1,
    "user": {
        "id": 1,
        "email": "driver@example.com",
        "first_name": "John",
        "last_name": "Driver",
        "user_type": "driver",
        "phone_number": "+255123456789"
    },
    "license_number": "DL123456",
    "vehicle_type": "bike",
    "vehicle_number": "MC123",
    "vehicle_model": "Honda CB150",
    "is_available": true,
    "is_verified": false,
    "is_online": true,
    "current_latitude": null,
    "current_longitude": null,
    "last_location_update": null,
    "rating": 4.5,
    "total_deliveries": 25,
    "total_orders": 30,
    "completed_orders": 25,
    "created_at": "2025-08-19T10:00:00Z",
    "approved_at": null
}
```

### 2. **POST Create Driver Profile**
```
POST /api/auth/driver/profile/create
```
**Description**: Create a new driver profile for authenticated driver users

**Headers**:
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Request Body**:
```json
{
    "license_number": "DL123456",
    "vehicle_type": "bike",
    "vehicle_number": "MC123",
    "vehicle_model": "Honda CB150"
}
```

**Response** (201 Created):
```json
{
    "id": 1,
    "license_number": "DL123456",
    "vehicle_type": "bike",
    "vehicle_number": "MC123",
    "vehicle_model": "Honda CB150"
}
```

**Error Responses**:
- **403 Forbidden**: Only users with driver type can create driver profile
- **400 Bad Request**: Driver profile already exists or validation errors

### 3. **PUT/PATCH Update Driver Profile**
```
PUT /api/auth/driver/profile
PATCH /api/auth/driver/profile
```
**Description**: Update the authenticated driver's profile information

**Headers**:
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Request Body** (partial update supported):
```json
{
    "vehicle_model": "Updated Honda CB150R",
    "vehicle_number": "MC456"
}
```

**Response** (200 OK):
```json
{
    "id": 1,
    "user": { ... },
    "license_number": "DL123456",
    "vehicle_type": "bike",
    "vehicle_number": "MC456",
    "vehicle_model": "Updated Honda CB150R",
    "is_available": true,
    "is_verified": false,
    "is_online": true,
    // ... other fields
}
```

### 4. **GET Driver Dashboard**
```
GET /api/auth/driver/dashboard
```
**Description**: Get comprehensive driver statistics and current status

**Response** (200 OK):
```json
{
    "driver_info": {
        "id": 1,
        "user": { ... },
        "license_number": "DL123456",
        // ... other profile fields
    },
    "statistics": {
        "total_orders": 30,
        "completed_orders": 25,
        "in_progress_orders": 1,
        "completion_rate": 83.33,
        "total_earnings": 75000.00,
        "average_rating": 4.5
    },
    "status": {
        "is_online": true,
        "is_available": true,
        "is_verified": false,
        "last_location_update": "2025-08-19T14:30:00Z"
    }
}
```

### 5. **POST Toggle Availability**
```
POST /api/auth/driver/toggle-availability
```
**Description**: Toggle driver availability for receiving new orders

**Response** (200 OK):
```json
{
    "message": "Driver availability set to available",
    "is_available": true,
    "is_online": true
}
```

### 6. **POST Toggle Online Status**
```
POST /api/auth/driver/toggle-online
```
**Description**: Toggle driver online/offline status

**Response** (200 OK):
```json
{
    "message": "Driver is now online",
    "is_online": true,
    "is_available": true
}
```

## Field Descriptions

### Driver Profile Fields

| Field | Type | Description | Read-Only |
|-------|------|-------------|-----------|
| `id` | Integer | Unique driver profile ID | Yes |
| `user` | Object | User information (name, email, etc.) | Yes |
| `license_number` | String | Driver's license number | No |
| `vehicle_type` | String | Type of vehicle (bike, car, etc.) | No |
| `vehicle_number` | String | Vehicle registration number | No |
| `vehicle_model` | String | Vehicle model/make | No |
| `is_available` | Boolean | Available for new orders | No |
| `is_verified` | Boolean | Profile verified by admin | Yes |
| `is_online` | Boolean | Currently online | No |
| `current_latitude` | Decimal | Current GPS latitude | Yes |
| `current_longitude` | Decimal | Current GPS longitude | Yes |
| `last_location_update` | DateTime | Last location update time | Yes |
| `rating` | Decimal | Average customer rating | Yes |
| `total_deliveries` | Integer | Total completed deliveries | Yes |
| `total_orders` | Integer | Total assigned orders | Yes |
| `completed_orders` | Integer | Successfully completed orders | Yes |
| `created_at` | DateTime | Profile creation date | Yes |
| `approved_at` | DateTime | Admin approval date | Yes |

## Validation Rules

1. **License Number**: Must be unique across all drivers
2. **Vehicle Number**: Must be unique across all drivers
3. **Vehicle Type**: Must be one of the predefined choices (currently: 'bike')
4. **User Type**: Only users with `user_type='driver'` can create/access driver profiles

## Permissions

- **Authentication Required**: All endpoints require valid JWT token
- **Driver Type Only**: Only users with `user_type='driver'` can access these endpoints
- **Profile Ownership**: Drivers can only access/modify their own profiles

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 401 | Unauthorized | Invalid or missing JWT token |
| 403 | Only drivers can access driver profile | User is not of type 'driver' |
| 404 | Driver profile not found | Driver profile doesn't exist |
| 400 | Driver profile already exists | Trying to create duplicate profile |
| 400 | License/vehicle number already registered | Duplicate license or vehicle number |

## Integration with Order System

The driver profile integrates seamlessly with the order management system:

- **Order Assignment**: Only available and verified drivers receive order notifications
- **Location Tracking**: Driver location is updated in real-time during deliveries
- **Statistics**: Dashboard shows real-time order and earnings data
- **Availability Management**: Drivers can control when they receive new orders

## Usage Examples

### Create Driver Profile
```bash
curl -X POST "http://localhost:8000/api/auth/driver/profile/create" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "license_number": "DL789012",
    "vehicle_type": "bike",
    "vehicle_number": "MC789",
    "vehicle_model": "Yamaha FZ150"
  }'
```

### Update Driver Profile
```bash
curl -X PATCH "http://localhost:8000/api/auth/driver/profile" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_model": "Yamaha FZ150 V2"
  }'
```

### Get Driver Dashboard
```bash
curl -X GET "http://localhost:8000/api/auth/driver/dashboard" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Toggle Availability
```bash
curl -X POST "http://localhost:8000/api/auth/driver/toggle-availability" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

The driver profile system is now fully integrated with the notification system, ensuring drivers receive real-time updates about new orders, status changes, and location requests.
