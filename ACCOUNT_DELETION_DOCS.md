# Account Deletion APIs Documentation

## Overview
The YumBackend authentication system provides comprehensive account deletion functionality including:
- **Soft Delete**: Temporarily delete accounts (can be restored within 30 days)
- **Hard Delete**: Permanently delete accounts (cannot be restored)
- **Account Restoration**: Restore soft-deleted accounts
- **Admin Management**: Admin tools for managing user account deletions

## API Endpoints

### 🔹 User Account Deletion

#### Soft Delete Account
**POST** `/api/auth/account/soft-delete`
- **Authentication**: Required
- **Description**: Temporarily delete the authenticated user's account
- **Restoration**: Account can be restored within 30 days

**Request Body:**
```json
{
    "reason": "No longer need the service",
    "confirm_deletion": true
}
```

**Response (200 OK):**
```json
{
    "message": "Account has been successfully deleted. You can restore it within 30 days by contacting support.",
    "deleted_at": "2025-08-21T10:30:00Z",
    "can_restore_until": "2025-09-20T10:30:00Z"
}
```

#### Hard Delete Account
**DELETE** `/api/auth/account/hard-delete`
- **Authentication**: Required
- **Description**: Permanently delete the authenticated user's account
- **Warning**: This action cannot be undone

**Request Body:**
```json
{
    "reason": "Want permanent deletion",
    "confirm_deletion": true
}
```

**Response (200 OK):**
```json
{
    "message": "Account testuser@example.com has been permanently deleted.",
    "deleted_user_id": 123
}
```

### 🔹 Account Restoration

#### Restore Deleted Account
**POST** `/api/auth/account/restore`
- **Authentication**: Not required
- **Description**: Restore a soft-deleted account using email and password

**Request Body:**
```json
{
    "email": "user@example.com",
    "password": "userpassword123"
}
```

**Response (200 OK):**
```json
{
    "message": "Account has been successfully restored.",
    "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
    "user": {
        "id": 123,
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "user_type": "customer"
    }
}
```

### 🔹 Account Status

#### Check Account Deletion Status
**GET** `/api/auth/account/status`
- **Authentication**: Optional
- **Description**: Check if an account is deleted and restoration status

**For authenticated users:**
```
GET /api/auth/account/status
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

**For checking by email (works for deleted accounts):**
```
GET /api/auth/account/status?email=user@example.com
```

**Response for Active Account:**
```json
{
    "is_deleted": false,
    "message": "Account is active"
}
```

**Response for Deleted Account:**
```json
{
    "is_deleted": true,
    "deleted_at": "2025-08-21T10:30:00Z",
    "deletion_reason": "User requested account deletion",
    "days_since_deletion": 5,
    "can_restore": true,
    "restore_deadline": "2025-09-20T10:30:00Z"
}
```

### 🔹 Admin Account Management

#### List Deleted Accounts
**GET** `/api/auth/admin/accounts`
- **Authentication**: Required (Admin only)
- **Description**: List all soft-deleted accounts

**Query Parameters:**
- `days`: Filter accounts deleted within X days

**Request:**
```
GET /api/auth/admin/accounts?days=7
Authorization: Token admin_token_here
```

**Response:**
```json
{
    "deleted_accounts": [
        {
            "id": 123,
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "user_type": "customer",
            "deleted_at": "2025-08-21T10:30:00Z",
            "deletion_reason": "User requested deletion",
            "days_since_deletion": 5
        }
    ],
    "total_count": 1
}
```

#### Admin Delete Account
**POST** `/api/auth/admin/accounts`
- **Authentication**: Required (Admin only)
- **Description**: Admin can soft delete or hard delete any user account

**Request Body:**
```json
{
    "user_id": 123,
    "deletion_type": "soft",
    "reason": "Admin decision - terms violation"
}
```

**Deletion Types:**
- `"soft"`: Soft delete (can be restored)
- `"hard"`: Permanent deletion

**Response (200 OK):**
```json
{
    "message": "User user@example.com has been soft deleted by admin.",
    "deletion_type": "soft",
    "deleted_at": "2025-08-21T10:30:00Z"
}
```

#### Admin Restore Account
**POST** `/api/auth/admin/accounts/{user_id}/restore`
- **Authentication**: Required (Admin only)
- **Description**: Admin restore any soft-deleted account

**Request:**
```
POST /api/auth/admin/accounts/123/restore
Authorization: Token admin_token_here
```

**Response (200 OK):**
```json
{
    "message": "User user@example.com has been successfully restored by admin.",
    "restored_user": {
        "id": 123,
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "user_type": "customer",
        "restored_at": "2025-08-21T11:00:00Z"
    }
}
```

## Security Features

### 🔒 Permission Controls
- **User Deletion**: Users can only delete their own accounts
- **Admin Powers**: Admins can delete/restore any account except superusers
- **Superuser Protection**: Superuser accounts cannot be deleted via API

### 🔒 Data Protection
- **Confirmation Required**: All deletions require explicit confirmation
- **Activity Logging**: All deletion activities are logged
- **Token Cleanup**: Authentication tokens are removed on deletion
- **IP Tracking**: User IP addresses are logged for security

### 🔒 Restoration Safeguards
- **Time Limit**: Soft-deleted accounts can only be restored within 30 days
- **Password Verification**: Account restoration requires password confirmation
- **Automatic Cleanup**: Accounts deleted >30 days ago cannot be restored

## Database Changes

The User model now includes additional fields for account deletion:

```python
class User(AbstractUser):
    # ... existing fields ...
    
    # Account status fields
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)
```

## Business Logic

### Soft Delete Behavior
When an account is soft deleted:
1. `is_deleted` = `True`
2. `deleted_at` = current timestamp
3. `is_active` = `False` (disables login)
4. Authentication tokens are deleted
5. Account becomes inaccessible but data is preserved

### Hard Delete Behavior
When an account is hard deleted:
1. All user data is permanently removed from database
2. Related objects are handled according to foreign key constraints
3. Action cannot be undone

### Restoration Process
When an account is restored:
1. `is_deleted` = `False`
2. `deleted_at` = `None`
3. `is_active` = `True` (re-enables login)
4. New authentication token is generated
5. User can access their account normally

## Usage Examples

### JavaScript/Frontend Examples

#### Soft Delete Account
```javascript
const deleteAccount = async () => {
    const response = await fetch('/api/auth/account/soft-delete', {
        method: 'POST',
        headers: {
            'Authorization': `Token ${userToken}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            reason: 'No longer need the service',
            confirm_deletion: true
        })
    });
    
    if (response.ok) {
        const data = await response.json();
        console.log('Account deleted:', data.message);
        // Redirect to goodbye page
    }
};
```

#### Check Account Status
```javascript
const checkAccountStatus = async (email) => {
    const response = await fetch(`/api/auth/account/status?email=${email}`);
    const data = await response.json();
    
    if (data.is_deleted) {
        console.log(`Account deleted ${data.days_since_deletion} days ago`);
        if (data.can_restore) {
            console.log('Account can still be restored');
        }
    }
};
```

#### Restore Account
```javascript
const restoreAccount = async (email, password) => {
    const response = await fetch('/api/auth/account/restore', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            email: email,
            password: password
        })
    });
    
    if (response.ok) {
        const data = await response.json();
        // Store new token and redirect to dashboard
        localStorage.setItem('token', data.token);
        window.location.href = '/dashboard';
    }
};
```

### Python/Backend Examples

#### Soft Delete User Programmatically
```python
from authentication.models import User

user = User.objects.get(email='user@example.com')
user.soft_delete(reason='Automated cleanup - inactive account')
```

#### Check Restoration Eligibility
```python
from django.utils import timezone
from datetime import timedelta

def can_restore_account(user):
    if not user.is_deleted or not user.deleted_at:
        return False
    
    days_since_deletion = (timezone.now() - user.deleted_at).days
    return days_since_deletion <= 30
```

#### Admin Bulk Operations
```python
from authentication.models import User
from django.utils import timezone
from datetime import timedelta

# Find accounts deleted more than 30 days ago
old_deleted_accounts = User.objects.filter(
    is_deleted=True,
    deleted_at__lt=timezone.now() - timedelta(days=30)
)

# These accounts can be permanently cleaned up
for account in old_deleted_accounts:
    print(f"Account {account.email} eligible for permanent deletion")
    # account.delete()  # Uncomment to actually delete
```

## Error Handling

### Common Error Responses

#### Validation Errors (400 Bad Request)
```json
{
    "confirm_deletion": ["You must confirm account deletion by setting this to true."]
}
```

#### Already Deleted (400 Bad Request)
```json
{
    "error": "Account is already deleted"
}
```

#### Restoration Expired (400 Bad Request)
```json
{
    "error": "Account cannot be restored. Deletion period has expired (>30 days)."
}
```

#### Unauthorized (401 Unauthorized)
```json
{
    "detail": "Authentication credentials were not provided."
}
```

#### Forbidden (403 Forbidden)
```json
{
    "detail": "You do not have permission to perform this action."
}
```

#### Not Found (404 Not Found)
```json
{
    "error": "User not found"
}
```

## Migration Guide

To add account deletion functionality to existing projects:

1. **Apply migrations:**
```bash
python manage.py makemigrations authentication
python manage.py migrate
```

2. **Update URLs:**
Add the new URL patterns to your `authentication/urls.py`

3. **Frontend Integration:**
Update your frontend to handle account deletion flows

4. **Admin Interface:**
The Django admin will automatically show the new fields

## Testing

Run the comprehensive test suite:
```bash
python manage.py test test_account_deletion
```

The test suite covers:
- Soft and hard deletion
- Account restoration
- Admin management features
- Permission validation
- Edge cases and error handling

## Best Practices

### For Users
1. **Soft Delete First**: Recommend soft delete for most use cases
2. **Clear Communication**: Explain the 30-day restoration period
3. **Data Export**: Offer data export before deletion
4. **Confirmation UI**: Implement clear confirmation dialogs

### For Admins
1. **Document Reasons**: Always provide clear deletion reasons
2. **Regular Cleanup**: Periodically clean up old deleted accounts
3. **Audit Trail**: Monitor deletion patterns for abuse
4. **Backup Strategy**: Ensure proper backups before hard deletions

### For Developers
1. **Handle Related Data**: Consider cascade effects of deletions
2. **Graceful Degradation**: Handle missing user references
3. **Performance**: Index deletion fields for large user bases
4. **Compliance**: Ensure GDPR/privacy law compliance
