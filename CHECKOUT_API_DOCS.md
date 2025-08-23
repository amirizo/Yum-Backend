# Cart & Checkout API Documentation

## Overview
Complete cart and checkout system with delivery fee calculation, payment processing, and order management.

## API Endpoints

### 1. Cart Management

#### Add to Cart
```
POST /api/orders/cart/add/
```
**Request:**
```json
{
  "product_id": 1,
  "quantity": 2,
  "special_instructions": "Extra spicy"
}
```

#### View Cart
```
GET /api/orders/cart/
```

#### Update Cart Item
```
PUT/PATCH /api/orders/cart/items/{product_id}/
```
**Request:**
```json
{
  "quantity": 3,
  "special_instructions": "Less spicy"
}
```

#### Remove from Cart
```
DELETE /api/orders/cart/items/{product_id}/remove/
```

#### Clear Cart
```
DELETE /api/orders/cart/clear/
```

### 2. Delivery Address Management

#### Get Saved Addresses
```
GET /api/orders/addresses/
```

#### Add New Address
```
POST /api/orders/addresses/
```
**Request:**
```json
{
  "label": "Home",
  "street_address": "123 Main Street",
  "city": "Dar es Salaam",
  "latitude": -6.7924,
  "longitude": 39.2083,
  "is_default": true
}
```

#### Validate Address
```
POST /api/orders/addresses/validate/
```
**Request:**
```json
{
  "address": "University of Dar es Salaam, Dar es Salaam",
  "latitude": -6.7924,
  "longitude": 39.2083
}
```

### 3. Delivery Fee Calculation

#### Calculate Delivery Preview
```
POST /api/orders/delivery/calculate/
```
**Request:**
```json
{
  "vendor_id": 1,
  "customer_latitude": -6.8104,
  "customer_longitude": 39.2083
}
```

**Response:**
```json
{
  "vendor_name": "Pizza Palace",
  "vendor_address": "Kivukoni Front, Dar es Salaam",
  "distance_km": 2.5,
  "delivery_fee": 5000,
  "currency": "TSH",
  "estimated_delivery_time": 45,
  "calculation_method": "≤3km: 2000 TSH/km, ≥4km: 700 TSH/km",
  "message": "Delivery fee calculated for 2.50km distance"
}
```

### 4. Checkout Process

#### Calculate Checkout Totals
```
POST /api/orders/checkout/
```
**Request:**
```json
{
  "vendor_id": 1,
  "delivery_address": {
    "address": "University of Dar es Salaam",
    "latitude": -6.7924,
    "longitude": 39.2083,
    "city": "Dar es Salaam",
    "delivery_instructions": "Gate 1, near library"
  },
  "payment_method": {
    "payment_type": "mobile_money",
    "phone_number": "+255123456789",
    "provider": "mix_by_yas"
  },
  "special_instructions": "Call when you arrive",
  "save_address": true,
  "address_label": "University"
}
```

**Response:**
```json
{
  "checkout_id": "CHK_1_1640995200",
  "vendor": {
    "id": 1,
    "name": "Pizza Palace",
    "address": "Kivukoni Front, Dar es Salaam",
    "phone": "+255123456789",
    "minimum_order_amount": 10000
  },
  "cart_items": [
    {
      "product_id": 1,
      "product_name": "Margherita Pizza",
      "product_price": 15000,
      "quantity": 2,
      "total_price": 30000,
      "special_instructions": "Extra cheese"
    }
  ],
  "pricing": {
    "subtotal": 30000,
    "delivery_fee": 5000,
    "tax_amount": 0,
    "total_amount": 35000,
    "currency": "TSH"
  },
  "delivery_info": {
    "distance_km": 2.5,
    "estimated_delivery_time": 45,
    "delivery_calculation": "≤3km rate: 2.50km × 2000 TSH = 5000 TSH",
    "address": {
      "address": "University of Dar es Salaam",
      "latitude": -6.7924,
      "longitude": 39.2083
    }
  },
  "payment_info": {
    "selected_method": {
      "payment_type": "mobile_money",
      "phone_number": "+255123456789"
    },
    "accepted_methods": ["mobile_money", "card", "cash"]
  },
  "validation": {
    "can_proceed": true,
    "message": "Checkout validation successful. Ready to proceed with payment."
  }
}
```

### 5. Payment Processing

#### Create Order and Payment
```
POST /api/payments/create-order-and-payment/
```
**Request:**
```json
{
  "vendor_id": 1,
  "delivery_address": {
    "address": "University of Dar es Salaam",
    "latitude": -6.7924,
    "longitude": 39.2083
  },
  "payment_method": {
    "payment_type": "mobile_money",
    "phone_number": "+255123456789",
    "provider": "mix_by_yas"
  },
  "special_instructions": "Call when you arrive"
}
```

**Response (Mobile Money):**
```json
{
  "success": true,
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_number": "ORD12345",
  "payment_id": 123,
  "status": "pending",
  "message": "Order created and USSD push sent to your phone. Please complete payment.",
  "payment_type": "mobile_money",
  "total_amount": 35000.0,
  "delivery_fee": 5000.0,
  "subtotal": 30000.0,
  "estimated_delivery_time": 45
}
```

#### Check Payment Status
```
GET /api/payments/status/{payment_id}/
```

**Response:**
```json
{
  "payment_id": 123,
  "status": "succeeded",
  "payment_type": "mobile_money",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_number": "ORD12345",
  "amount": 35000.0,
  "currency": "TZS",
  "processed_at": "2024-01-01T12:00:00Z",
  "message": "Payment succeeded"
}
```

### 6. Testing Endpoints

#### Test Delivery Calculations
```
GET /api/orders/test/delivery-calculations/
```

#### Custom Delivery Test
```
POST /api/orders/test/custom-delivery/
```
**Request:**
```json
{
  "vendor_latitude": -6.7924,
  "vendor_longitude": 39.2083,
  "customer_latitude": -6.8104,
  "customer_longitude": 39.2083
}
```

## Delivery Fee Calculation Rules

### Rule 1: Distance ≤ 3km
- **Rate**: 2000 TSH per km
- **Formula**: `distance_km × 2000`
- **Example**: 2.5km → 2.5 × 2000 = 5000 TSH

### Rule 2: Distance ≥ 4km  
- **Rate**: 700 TSH per km
- **Formula**: `distance_km × 700`
- **Example**: 5km → 5 × 700 = 3500 TSH

## Payment Methods Supported

### 1. Mobile Money
- **Providers**: Mix by YAS (all networks), Vodacom M-Pesa, Airtel Money, Tigo Pesa, Halo Pesa
- **Process**: USSD push to customer phone
- **Currency**: TZS

### 2. Card Payment
- **Process**: Redirect to ClickPesa payment page
- **Currency**: USD (converted by ClickPesa)

### 3. Cash on Delivery
- **Process**: Admin approval required
- **Payment**: Collected by driver

## Error Handling

### Common Error Responses

#### Cart Empty
```json
{
  "error": "Cart is empty for this vendor"
}
```

#### Minimum Order Not Met
```json
{
  "error": "Minimum order amount is 10000 TSH. Current total: 8000 TSH"
}
```

#### Vendor Inactive
```json
{
  "error": "Vendor not found or inactive"
}
```

#### Invalid Address
```json
{
  "error": "Invalid latitude. Must be between -90 and 90"
}
```

#### Payment Failed
```json
{
  "error": "Mobile money payment failed",
  "details": "Insufficient balance"
}
```

## Workflow Summary

1. **Add items to cart** → `POST /api/orders/cart/add/`
2. **Validate delivery address** → `POST /api/orders/addresses/validate/`
3. **Calculate delivery preview** → `POST /api/orders/delivery/calculate/`
4. **Checkout calculation** → `POST /api/orders/checkout/`
5. **Create order and payment** → `POST /api/payments/create-order-and-payment/`
6. **Check payment status** → `GET /api/payments/status/{payment_id}/`
7. **Order completion** → Automatic via webhooks

## Authentication
- Most endpoints require authentication except cart viewing and testing endpoints
- Use `Authorization: Bearer <token>` header
- Anonymous users can add to cart (session-based)
