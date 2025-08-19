# Vendor Category Management API Documentation

## Overview
This API allows vendors to manage their product categories. Vendors can create, read, update, and delete their own categories while maintaining separation from other vendors' categories.

## Endpoints

### 1. List All Categories (Public)
**GET** `/api/orders/product/categories/`

**Description**: Public endpoint to view all active categories from all vendors and global categories.

**Authentication**: Not required

**Query Parameters**:
- `category_type`: Filter by type (`food` or `grocery`)
- `vendor`: Filter by vendor ID

**Response Example**:
```json
[
    {
        "id": 1,
        "name": "Pizza",
        "description": "All types of pizza",
        "image": "/media/categories/pizza.jpg",
        "category_type": "food",
        "is_active": true,
        "product_count": 5,
        "vendor_name": "Pizza Palace",
        "created_at": "2025-01-01T10:00:00Z"
    }
]
```

### 2. Vendor Category Management (CRUD)

#### List/Create Vendor Categories
**GET/POST** `/api/orders/vendor/categories/`

**Authentication**: Required (Vendor only)

**GET Response Example**:
```json
[
    {
        "id": 1,
        "name": "Main Dishes",
        "description": "Primary food items",
        "image": "/media/categories/main.jpg",
        "category_type": "food",
        "is_active": true,
        "product_count": 8,
        "created_at": "2025-01-01T10:00:00Z"
    }
]
```

**POST Request Body**:
```json
{
    "name": "Desserts",
    "description": "Sweet treats and desserts",
    "category_type": "food",
    "image": "base64_or_file_upload",
    "is_active": true
}
```

**Query Parameters** (GET):
- `category_type`: Filter by type
- `is_active`: Filter by active status
- `search`: Search in name and description
- `ordering`: Sort by name, created_at

#### Retrieve/Update/Delete Specific Category
**GET/PUT/PATCH/DELETE** `/api/orders/vendor/categories/{id}/`

**Authentication**: Required (Vendor only - own categories)

**PUT/PATCH Request Body**:
```json
{
    "name": "Updated Category Name",
    "description": "Updated description",
    "is_active": false
}
```

**DELETE**: 
- Only allowed if category has no products
- Returns 204 on success
- Returns 400 if category has products

#### Category Statistics
**GET** `/api/orders/vendor/categories/stats/`

**Authentication**: Required (Vendor only)

**Response Example**:
```json
{
    "total_categories": 5,
    "active_categories": 4,
    "inactive_categories": 1,
    "categories_by_type": {
        "food": 3,
        "grocery": 2
    },
    "categories_with_products": 3,
    "empty_categories": 2
}
```

## Model Changes

### Category Model Updates
- Added `vendor` field (ForeignKey to Vendor, nullable for global categories)
- Changed `name` from unique to unique_together with vendor
- Added proper string representation with vendor info
- Related name changed to `product_categories` to avoid conflicts

### Database Migration
The migration `0003_category_vendor_alter_category_name_and_more.py` includes:
- Adding vendor field to Category
- Altering unique constraint for name field
- Setting up unique_together constraint

## Validation Rules

1. **Category Name**: Must be unique per vendor (not globally unique)
2. **Vendor Assignment**: Automatically set to current user's vendor profile
3. **Deletion**: Only allowed if no products are assigned to the category
4. **Access Control**: Vendors can only manage their own categories

## Error Handling

### Common Error Responses

**403 Forbidden** - Non-vendor trying to access vendor endpoints:
```json
{
    "detail": "Only vendors can access this endpoint"
}
```

**400 Bad Request** - Duplicate category name:
```json
{
    "name": ["You already have a category with this name."]
}
```

**400 Bad Request** - Deleting category with products:
```json
{
    "detail": "Cannot delete category that has products. Please remove or reassign products first."
}
```

## Usage Examples

### Creating a New Category
```bash
curl -X POST /api/orders/vendor/categories/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Beverages",
    "description": "Hot and cold drinks",
    "category_type": "food",
    "is_active": true
  }'
```

### Updating a Category
```bash
curl -X PATCH /api/orders/vendor/categories/1/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description for beverages"
  }'
```

### Getting Category Statistics
```bash
curl -X GET /api/orders/vendor/categories/stats/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Integration Notes

- Categories are automatically linked to products when vendors create products
- The existing product management system works seamlessly with vendor-specific categories
- Global categories (vendor=null) remain available for admin-created universal categories
- Category images are stored in `/media/categories/` directory

## Security Features

- Vendors can only see and modify their own categories
- Authentication required for all category management operations
- Proper permission checks prevent unauthorized access
- Validation ensures data integrity
