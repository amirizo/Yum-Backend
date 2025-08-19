# Vendor Category API Test Examples

## Test the API endpoints (requires authentication)

### 1. Get vendor's categories
```bash
curl -X GET "http://localhost:8000/api/orders/vendor/categories/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 2. Create a new category
```bash
curl -X POST "http://localhost:8000/api/orders/vendor/categories/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Appetizers",
    "description": "Starter dishes and small plates",
    "category_type": "food",
    "is_active": true
  }'
```

### 3. Update a category
```bash
curl -X PATCH "http://localhost:8000/api/orders/vendor/categories/1/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated: Starter dishes and appetizers"
  }'
```

### 4. Get category statistics
```bash
curl -X GET "http://localhost:8000/api/orders/vendor/categories/stats/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 5. Delete a category (only if no products)
```bash
curl -X DELETE "http://localhost:8000/api/orders/vendor/categories/1/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 6. Public categories list
```bash
curl -X GET "http://localhost:8000/api/orders/product/categories/"
```

### 7. Search categories
```bash
curl -X GET "http://localhost:8000/api/orders/vendor/categories/?search=pizza" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 8. Filter by category type
```bash
curl -X GET "http://localhost:8000/api/orders/vendor/categories/?category_type=food" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Expected Responses

### Successful Category Creation (201 Created)
```json
{
    "id": 1,
    "name": "Appetizers",
    "description": "Starter dishes and small plates",
    "image": null,
    "category_type": "food",
    "is_active": true,
    "product_count": 0,
    "created_at": "2025-08-19T10:00:00Z"
}
```

### Category Statistics Response
```json
{
    "total_categories": 5,
    "active_categories": 4,
    "inactive_categories": 1,
    "categories_by_type": {
        "food": 3,
        "grocery": 2
    },
    "categories_with_products": 2,
    "empty_categories": 3
}
```

### Error: Duplicate Category Name (400 Bad Request)
```json
{
    "name": ["You already have a category with this name."]
}
```

### Error: Permission Denied (403 Forbidden)
```json
{
    "detail": "Only vendors can access this endpoint"
}
```
