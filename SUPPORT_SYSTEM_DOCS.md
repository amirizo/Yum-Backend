# Support System API Documentation

## Overview
The YumBackend support system provides comprehensive customer support functionality including:
- Support ticket management with messaging
- Customer feedback collection and management
- FAQ system with voting capabilities
- Support metrics and analytics

## API Endpoints

### Support Tickets

#### List/Create Tickets
- **GET/POST** `/api/support/tickets/`
- **Authentication**: Required
- **Permissions**: Authenticated users can view their own tickets, staff can view all

**POST Data Example:**
```json
{
    "subject": "Order Issue",
    "description": "My order was delivered cold",
    "category": "delivery",
    "priority": "high"
}
```

#### Ticket Detail
- **GET/PUT/PATCH** `/api/support/tickets/{id}/`
- **Authentication**: Required
- **Permissions**: Users can view/edit their own tickets, staff can view/edit all

#### Add Message to Ticket
- **POST** `/api/support/tickets/{id}/messages/`
- **Authentication**: Required

**POST Data Example:**
```json
{
    "content": "Thank you for your response. The issue is resolved.",
    "message_type": "message"
}
```

#### Close Ticket
- **POST** `/api/support/tickets/{id}/close/`
- **Authentication**: Required
- **Permissions**: Users can close their own tickets, staff can close any

### Feedback System

#### Submit/List Feedback
- **GET/POST** `/api/support/feedback/`
- **Authentication**: Optional (anonymous feedback allowed)

**POST Data Example (Authenticated):**
```json
{
    "feedback_type": "suggestion",
    "subject": "App Improvement",
    "description": "Please add dark mode",
    "rating": 4
}
```

**POST Data Example (Anonymous):**
```json
{
    "feedback_type": "bug_report",
    "subject": "Found a bug",
    "description": "Bug description",
    "rating": 3,
    "email": "user@example.com",
    "name": "John Doe"
}
```

#### Admin Feedback Management
- **GET/PUT/PATCH** `/api/support/feedback/{id}/`
- **Authentication**: Required
- **Permissions**: Staff only

#### Respond to Feedback
- **POST** `/api/support/feedback/{id}/respond/`
- **Authentication**: Required
- **Permissions**: Staff only

**POST Data Example:**
```json
{
    "admin_response": "Thank you for your feedback. We'll consider this feature."
}
```

### FAQ System

#### List FAQ Categories
- **GET** `/api/support/faq/categories/`
- **Authentication**: Not required

#### FAQ Category Detail
- **GET** `/api/support/faq/categories/{id}/`
- **Authentication**: Not required

#### List FAQ Items
- **GET** `/api/support/faq/items/`
- **Authentication**: Not required
- **Query Parameters:**
  - `category`: Filter by category ID
  - `search`: Search in questions and answers

#### FAQ Item Detail
- **GET** `/api/support/faq/items/{id}/`
- **Authentication**: Not required
- **Note**: Increments view count automatically

#### Vote on FAQ Item
- **POST** `/api/support/faq/items/{id}/vote/`
- **Authentication**: Required

**POST Data Example:**
```json
{
    "vote": "helpful"
}
```

**Vote Options:** `helpful`, `not_helpful`

### Admin FAQ Management

#### Manage FAQ Categories
- **GET/POST/PUT/PATCH/DELETE** `/api/support/admin/faq/categories/`
- **Authentication**: Required
- **Permissions**: Staff only

#### Manage FAQ Items
- **GET/POST/PUT/PATCH/DELETE** `/api/support/admin/faq/items/`
- **Authentication**: Required
- **Permissions**: Staff only

### Analytics & Metrics

#### Support Statistics
- **GET** `/api/support/stats/`
- **Authentication**: Required
- **Permissions**: Staff only

**Response Example:**
```json
{
    "total_tickets": 150,
    "open_tickets": 25,
    "closed_tickets": 125,
    "avg_resolution_time_hours": 18.5,
    "total_feedback": 75,
    "avg_feedback_rating": 4.2,
    "total_faq_items": 20,
    "total_faq_views": 1500
}
```

## Models

### SupportTicket
- **Fields**: ticket_number, user, subject, description, category, priority, status, assigned_to, etc.
- **Categories**: general, order, delivery, payment, account, technical
- **Priorities**: low, medium, high, urgent
- **Statuses**: open, in_progress, waiting_for_customer, resolved, closed

### TicketMessage
- **Fields**: ticket, sender, content, message_type, is_internal, attachments
- **Types**: message, note, status_change

### Feedback
- **Fields**: user, feedback_type, subject, description, rating, status, etc.
- **Types**: general, bug_report, feature_request, suggestion, complaint
- **Statuses**: pending, reviewed, responded, closed

### FAQCategory
- **Fields**: name, description, order, is_active

### FAQItem
- **Fields**: category, question, answer, order, views_count, helpful_count, not_helpful_count

### FAQVote
- **Fields**: faq_item, user, vote, ip_address
- **Constraints**: One vote per user per FAQ item

### SupportMetrics
- **Fields**: date, tickets_created, tickets_resolved, avg_resolution_time_hours, feedback_submitted, avg_rating

## Security Features

- **Authentication**: Token-based authentication for user-specific operations
- **Permission System**: Role-based access (users vs staff)
- **Anonymous Support**: Anonymous feedback submission allowed
- **Rate Limiting**: Built-in protection against spam (recommended to add)
- **Data Validation**: Comprehensive input validation and sanitization

## Usage Examples

### Create a Support Ticket
```python
import requests

headers = {'Authorization': 'Token your_token_here'}
data = {
    'subject': 'Order Issue',
    'description': 'My order was delivered to wrong address',
    'category': 'delivery',
    'priority': 'high'
}

response = requests.post(
    'http://localhost:8000/api/support/tickets/',
    headers=headers,
    json=data
)
```

### Submit Anonymous Feedback
```python
import requests

data = {
    'feedback_type': 'suggestion',
    'subject': 'App Improvement',
    'description': 'Please add push notifications',
    'rating': 4,
    'email': 'user@example.com',
    'name': 'Anonymous User'
}

response = requests.post(
    'http://localhost:8000/api/support/feedback/',
    json=data
)
```

### Get FAQ Items
```python
import requests

# Get all FAQ items
response = requests.get('http://localhost:8000/api/support/faq/items/')

# Search FAQ items
response = requests.get(
    'http://localhost:8000/api/support/faq/items/',
    params={'search': 'delivery time'}
)

# Filter by category
response = requests.get(
    'http://localhost:8000/api/support/faq/items/',
    params={'category': 1}
)
```

## Setup Instructions

1. **Install Requirements**: Ensure Django and DRF are installed
2. **Add to INSTALLED_APPS**: Add 'support' to your Django settings
3. **Run Migrations**: `python manage.py makemigrations support && python manage.py migrate`
4. **Populate FAQ Data**: `python manage.py populate_faq`
5. **Include URLs**: Add support URLs to your main urlpatterns
6. **Configure Permissions**: Set up appropriate user permissions

## Testing

Run the comprehensive test suite:
```bash
python manage.py test support
```

The test suite includes:
- API endpoint testing
- Model validation
- Permission testing
- Anonymous vs authenticated access
- Voting system functionality
- Data integrity checks

## Admin Interface

The support system includes a comprehensive Django admin interface with:
- **Ticket Management**: View, edit, and manage support tickets
- **Message Threading**: View ticket conversation history
- **Feedback Management**: Review and respond to customer feedback
- **FAQ Management**: Manage categories and items with inline editing
- **Metrics Dashboard**: View support statistics and trends

Access the admin interface at `/admin/` after creating a superuser account.
