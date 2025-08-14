from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import serializers
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import Q, Avg, Count, Sum, F
from django.utils import timezone
from datetime import timedelta
from .models import (
    Category, Product, ProductImage, ProductVariant, ProductReview,
    DeliveryAddress, Order, OrderItem, OrderStatusHistory, Review
)

from .serializers import (
    CategorySerializer, ProductSerializer, ProductCreateUpdateSerializer,
    VendorProductListSerializer, ProductImageSerializer, ProductVariantSerializer,
    ProductReviewSerializer, DeliveryAddressSerializer, OrderCreateSerializer,
    OrderSerializer, OrderStatusHistorySerializer, OrderStatusUpdateSerializer,
    ReviewSerializer,OrderItemSerializer
)
from .services import OrderNotificationService


# Category Views
class CategoryListView(generics.ListCreateAPIView):
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['parent', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'name', 'created_at']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        return Category.objects.filter(is_active=True)
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), permissions.IsAdminUser()]
        return [permissions.AllowAny()]

class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

# Product Views
class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'vendor', 'status', 'is_featured', 'is_vegetarian', 'is_vegan', 'is_gluten_free']
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Product.objects.filter(status='active', is_available=True)
        
        # Filter by vendor business type if specified
        vendor_type = self.request.query_params.get('vendor_type')
        if vendor_type:
            queryset = queryset.filter(vendor__vendor_profile__business_type=vendor_type)
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        # Filter by rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.annotate(
                avg_rating=Avg('product_reviews__rating')
            ).filter(avg_rating__gte=min_rating)
        
        return queryset.select_related('vendor', 'category').prefetch_related(
            'images', 'variants', 'product_reviews'
        )

class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(status='active', is_available=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

# Vendor Product Management Views
class VendorProductListView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'is_available', 'is_featured']
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['name', 'price', 'inventory_quantity', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return VendorProductListSerializer
        return ProductCreateUpdateSerializer

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return Product.objects.none()
        return Product.objects.filter(vendor=self.request.user)

class VendorProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ProductSerializer
        return ProductCreateUpdateSerializer

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return Product.objects.none()
        return Product.objects.filter(vendor=self.request.user)

# Product Image Management
class ProductImageListView(generics.ListCreateAPIView):
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        product_id = self.kwargs['product_id']
        if self.request.user.user_type != 'vendor':
            return ProductImage.objects.none()
        return ProductImage.objects.filter(
            product_id=product_id,
            product__vendor=self.request.user
        )

    def perform_create(self, serializer):
        product_id = self.kwargs['product_id']
        product = Product.objects.get(id=product_id, vendor=self.request.user)
        serializer.save(product=product)

class ProductImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return ProductImage.objects.none()
        return ProductImage.objects.filter(product__vendor=self.request.user)

# Product Variant Management
class ProductVariantListView(generics.ListCreateAPIView):
    serializer_class = ProductVariantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        product_id = self.kwargs['product_id']
        if self.request.user.user_type != 'vendor':
            return ProductVariant.objects.none()
        return ProductVariant.objects.filter(
            product_id=product_id,
            product__vendor=self.request.user
        )

    def perform_create(self, serializer):
        product_id = self.kwargs['product_id']
        product = Product.objects.get(id=product_id, vendor=self.request.user)
        serializer.save(product=product)

class ProductVariantDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductVariantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return ProductVariant.objects.none()
        return ProductVariant.objects.filter(product__vendor=self.request.user)

# Product Review Views
class ProductReviewListView(generics.ListCreateAPIView):
    serializer_class = ProductReviewSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['rating', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        product_id = self.kwargs['product_id']
        return ProductReview.objects.filter(
            product_id=product_id,
            is_approved=True
        ).select_related('customer')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        product_id = self.kwargs['product_id']
        product = Product.objects.get(id=product_id)
        
        # Check if user has purchased this product
        has_purchased = OrderItem.objects.filter(
            order__customer=self.request.user,
            order__status='delivered',
            product=product
        ).exists()
        
        serializer.save(
            product=product,
            customer=self.request.user,
            is_verified_purchase=has_purchased
        )

# Delivery Address Views
class DeliveryAddressListView(generics.ListCreateAPIView):
    serializer_class = DeliveryAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DeliveryAddress.objects.filter(user=self.request.user)

class DeliveryAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DeliveryAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DeliveryAddress.objects.filter(user=self.request.user)

# Order Views
class OrderCreateView(generics.CreateAPIView):
    serializer_class = OrderCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_status']
    ordering_fields = ['created_at', 'total_amount']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'customer':
            return Order.objects.filter(customer=user)
        elif user.user_type == 'vendor':
            return Order.objects.filter(vendor=user)
        elif user.user_type == 'driver':
            return Order.objects.filter(driver=user)
        else:
            return Order.objects.all()

class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'customer':
            return Order.objects.filter(customer=user)
        elif user.user_type == 'vendor':
            return Order.objects.filter(vendor=user)
        elif user.user_type == 'driver':
            return Order.objects.filter(driver=user)
        else:
            return Order.objects.all()

class OrderStatusUpdateView(generics.UpdateAPIView):
    serializer_class = OrderStatusUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'vendor':
            return Order.objects.filter(vendor=user)
        elif user.user_type == 'driver':
            return Order.objects.filter(driver=user)
        else:
            return Order.objects.all()

# Enhanced Vendor Order Management Views
class VendorOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'customer__first_name', 'customer__last_name', 'customer__email']
    ordering_fields = ['created_at', 'total_amount', 'estimated_delivery_time']
    ordering = ['-created_at']

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return Order.objects.none()
        
        queryset = Order.objects.filter(vendor=self.request.user).select_related(
            'customer', 'driver', 'delivery_address'
        ).prefetch_related('items__product', 'status_history')
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # Filter by order value range
        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        if min_amount:
            queryset = queryset.filter(total_amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(total_amount__lte=max_amount)
        
        return queryset

class VendorOrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            return Order.objects.none()
        return Order.objects.filter(vendor=self.request.user).select_related(
            'customer', 'driver', 'delivery_address'
        ).prefetch_related('items__product', 'status_history')





class OrderStatusHistoryView(generics.ListAPIView):
    serializer_class = OrderStatusHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        order_id = self.kwargs['order_id']
        return OrderStatusHistory.objects.filter(order_id=order_id)

# Review Views
class OrderReviewCreateView(generics.CreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['order_id'] = self.kwargs['order_id']
        return context

    def perform_create(self, serializer):
        order_id = self.kwargs['order_id']
        order = Order.objects.get(id=order_id, customer=self.request.user)
        
        if order.status != 'delivered':
            raise serializers.ValidationError("Can only review delivered orders")
        
        serializer.save()

class ReviewListView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['vendor', 'overall_rating']
    ordering = ['-created_at']

    def get_queryset(self):
        return Review.objects.all()





# Dashboard Views
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def customer_dashboard(request):
    user = request.user
    if user.user_type != 'customer':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get customer statistics
    orders = Order.objects.filter(customer=user)
    total_orders = orders.count()
    pending_orders = orders.filter(status__in=['pending', 'confirmed', 'preparing', 'ready', 'picked_up', 'in_transit']).count()
    completed_orders = orders.filter(status='delivered').count()
    
    return Response({
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'recent_orders': OrderSerializer(orders[:5], many=True).data
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def vendor_dashboard(request):
    user = request.user
    if user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get vendor statistics
    orders = Order.objects.filter(vendor=user)
    products = Product.objects.filter(vendor=user)
    reviews = Review.objects.filter(vendor=user)
    
    total_orders = orders.count()
    pending_orders = orders.filter(status__in=['pending', 'confirmed']).count()
    total_products = products.count()
    average_rating = reviews.aggregate(avg_rating=Avg('overall_rating'))['avg_rating'] or 0
    
    return Response({
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_products': total_products,
        'average_rating': round(average_rating, 2),
        'recent_orders': OrderSerializer(orders[:5], many=True).data
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def driver_dashboard(request):
    user = request.user
    if user.user_type != 'driver':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get driver statistics
    orders = Order.objects.filter(driver=user)
    total_deliveries = orders.filter(status='delivered').count()
    active_orders = orders.filter(status__in=['picked_up', 'in_transit']).count()
    available_orders = Order.objects.filter(status='ready', driver__isnull=True).count()
    
    return Response({
        'total_deliveries': total_deliveries,
        'active_orders': active_orders,
        'available_orders': available_orders,
        'recent_orders': OrderSerializer(orders[:5], many=True).data
    })







@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_driver_to_order(request, order_id):
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can accept orders'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(id=order_id, status='ready', driver__isnull=True)
        order.driver = request.user
        order.status = 'picked_up'
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='picked_up',
            changed_by=request.user,
            notes='Order picked up by driver'
        )
        
        OrderNotificationService.send_order_picked_up_email(order)
        
        return Response({'message': 'Order assigned successfully'})
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or not available'}, status=status.HTTP_404_NOT_FOUND)



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reject_order(request, order_id):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Only vendors can reject orders'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(id=order_id, vendor=request.user, status='pending')
        rejection_reason = request.data.get('reason', 'No reason provided')
        
        # Process order rejection with email and refund
        success = OrderNotificationService.process_order_rejection(
            order=order,
            rejection_reason=rejection_reason,
            rejected_by=request.user
        )
        
        if success:
            return Response({'message': 'Order rejected successfully. Customer has been notified and refund is being processed.'})
        else:
            return Response({'error': 'Failed to process order rejection'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be rejected'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def accept_order(request, order_id):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Only vendors can accept orders'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(id=order_id, vendor=request.user, status='pending')
        
        # Calculate estimated delivery time
        preparation_time = request.data.get('preparation_time', 30)  # minutes
        estimated_delivery = timezone.now() + timezone.timedelta(minutes=preparation_time + 30)  # prep + delivery time
        
        # Update order status
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.estimated_delivery_time = estimated_delivery
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='confirmed',
            changed_by=request.user,
            notes=f'Order accepted by vendor. Estimated preparation time: {preparation_time} minutes'
        )
        
        # Send email notification
        OrderNotificationService.send_order_accepted_email(order)
        
        return Response({
            'message': 'Order accepted successfully. Customer has been notified.',
            'estimated_delivery_time': estimated_delivery
        })
        
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be accepted'}, status=status.HTTP_404_NOT_FOUND) 






@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def vendor_update_preparation_status(request, order_id):
    """Update order preparation status"""
    if request.user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    new_status = request.data.get('status')
    notes = request.data.get('notes', '')
    
    valid_statuses = ['confirmed', 'preparing', 'ready']
    if new_status not in valid_statuses:
        return Response({'error': f'Invalid status. Must be one of: {valid_statuses}'}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    try:
        order = Order.objects.get(id=order_id, vendor=request.user)
        
        # Validate status transition
        current_status = order.status
        if current_status == 'pending' and new_status != 'confirmed':
            return Response({'error': 'Must confirm order first'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        elif current_status == 'confirmed' and new_status not in ['preparing', 'ready']:
            return Response({'error': 'Invalid status transition'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        elif current_status == 'preparing' and new_status != 'ready':
            return Response({'error': 'Can only mark as ready from preparing'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        order.status = new_status
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
            changed_by=request.user,
            notes=notes or f'Order status updated to {new_status}'
        )
        
        # TODO: Send notification to customer and dispatch system
        
        return Response({
            'message': f'Order status updated to {new_status}',
            'order': OrderSerializer(order).data
        })
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_update_order_status(request):
    """Bulk update multiple orders status"""
    if request.user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    order_ids = request.data.get('order_ids', [])
    new_status = request.data.get('status')
    notes = request.data.get('notes', '')
    
    if not order_ids or not new_status:
        return Response({'error': 'order_ids and status are required'}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    valid_statuses = ['confirmed', 'preparing', 'ready', 'cancelled']
    if new_status not in valid_statuses:
        return Response({'error': f'Invalid status. Must be one of: {valid_statuses}'}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    orders = Order.objects.filter(id__in=order_ids, vendor=request.user)
    updated_count = 0
    
    for order in orders:
        # Basic validation - can be enhanced based on business rules
        if order.status in ['delivered', 'cancelled']:
            continue  # Skip completed orders
        
        order.status = new_status
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
            changed_by=request.user,
            notes=notes or f'Bulk update to {new_status}'
        )
        updated_count += 1
    
    return Response({
        'message': f'Updated {updated_count} orders',
        'updated_count': updated_count
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def vendor_order_analytics(request):
    """Get comprehensive order analytics for vendor"""
    if request.user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Date range filter
    days = int(request.query_params.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    orders = Order.objects.filter(vendor=request.user, created_at__gte=start_date)
    
    # Basic statistics
    total_orders = orders.count()
    completed_orders = orders.filter(status='delivered').count()
    cancelled_orders = orders.filter(status='cancelled').count()
    pending_orders = orders.filter(status='pending').count()
    
    # Revenue statistics
    total_revenue = orders.filter(status='delivered').aggregate(
        total=Sum('total_amount'))['total'] or 0
    average_order_value = orders.filter(status='delivered').aggregate(
        avg=Avg('total_amount'))['avg'] or 0
    
    # Order status distribution
    status_distribution = orders.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Daily order trends
    daily_orders = orders.extra(
        select={'day': 'date(created_at)'}
    ).values('day').annotate(
        count=Count('id'),
        revenue=Sum('total_amount')
    ).order_by('day')
    
    # Top selling products
    top_products = OrderItem.objects.filter(
        order__vendor=request.user,
        order__created_at__gte=start_date,
        order__status='delivered'
    ).values(
        'product__name'
    ).annotate(
        quantity_sold=Sum('quantity'),
        revenue=Sum('total_price')
    ).order_by('-quantity_sold')[:10]
    
    # Customer insights
    repeat_customers = orders.values('customer').annotate(
        order_count=Count('id')
    ).filter(order_count__gt=1).count()
    
    # Average preparation time
    avg_prep_time = orders.filter(
        status='delivered',
        confirmed_at__isnull=False
    ).aggregate(
        avg_time=Avg(
            F('estimated_delivery_time') - F('confirmed_at')
        )
    )['avg_time']
    
    return Response({
        'period': f'Last {days} days',
        'summary': {
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'cancelled_orders': cancelled_orders,
            'pending_orders': pending_orders,
            'completion_rate': round((completed_orders / total_orders * 100) if total_orders > 0 else 0, 2),
            'cancellation_rate': round((cancelled_orders / total_orders * 100) if total_orders > 0 else 0, 2),
        },
        'revenue': {
            'total_revenue': float(total_revenue),
            'average_order_value': float(average_order_value),
        },
        'trends': {
            'status_distribution': list(status_distribution),
            'daily_orders': list(daily_orders),
        },
        'products': {
            'top_selling': list(top_products),
        },
        'customers': {
            'repeat_customers': repeat_customers,
            'total_customers': orders.values('customer').distinct().count(),
        },
        'performance': {
            'average_preparation_time': str(avg_prep_time) if avg_prep_time else None,
        }
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def vendor_order_queue(request):
    """Get current order queue for kitchen display"""
    if request.user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get orders in preparation queue
    queue_orders = Order.objects.filter(
        vendor=request.user,
        status__in=['confirmed', 'preparing']
    ).select_related('customer').prefetch_related('items__product').order_by('confirmed_at')
    
    # Format for kitchen display
    queue_data = []
    for order in queue_orders:
        # Calculate time since confirmation
        time_since_confirmed = None
        if order.confirmed_at:
            time_since_confirmed = (timezone.now() - order.confirmed_at).total_seconds() / 60
        
        # Calculate estimated completion time
        total_prep_time = sum(item.product.preparation_time * item.quantity for item in order.items.all())
        
        queue_data.append({
            'order_id': str(order.id),
            'order_number': order.order_number,
            'customer_name': f"{order.customer.first_name} {order.customer.last_name}".strip() or order.customer.username,
            'status': order.status,
            'items': [
                {
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'special_instructions': item.special_instructions,
                    'preparation_time': item.product.preparation_time
                }
                for item in order.items.all()
            ],
            'total_prep_time': total_prep_time,
            'time_since_confirmed': round(time_since_confirmed) if time_since_confirmed else None,
            'confirmed_at': order.confirmed_at,
            'estimated_ready_time': order.estimated_delivery_time - timedelta(minutes=30) if order.estimated_delivery_time else None,
        })
    
    return Response({
        'queue': queue_data,
        'queue_length': len(queue_data),
        'average_wait_time': sum(item['total_prep_time'] for item in queue_data) / len(queue_data) if queue_data else 0
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def vendor_daily_summary(request):
    """Get daily summary for vendor"""
    if request.user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get today's date
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    # Today's orders
    today_orders = Order.objects.filter(
        vendor=request.user,
        created_at__date=today
    )
    
    # Statistics
    total_orders_today = today_orders.count()
    completed_today = today_orders.filter(status='delivered').count()
    pending_today = today_orders.filter(status='pending').count()
    revenue_today = today_orders.filter(status='delivered').aggregate(
        total=Sum('total_amount'))['total'] or 0
    
    # Upcoming orders (next few hours)
    upcoming_orders = Order.objects.filter(
        vendor=request.user,
        status__in=['confirmed', 'preparing'],
        estimated_delivery_time__lte=timezone.now() + timedelta(hours=2)
    ).order_by('estimated_delivery_time')
    
    return Response({
        'date': today,
        'summary': {
            'total_orders': total_orders_today,
            'completed_orders': completed_today,
            'pending_orders': pending_today,
            'revenue': float(revenue_today),
        },
        'upcoming_orders': OrderSerializer(upcoming_orders, many=True).data,
    })

# Dashboard and Analytics Views
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def vendor_product_analytics(request):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    products = Product.objects.filter(vendor=request.user)
    
    # Product statistics
    total_products = products.count()
    active_products = products.filter(status='active', is_available=True).count()
    out_of_stock = products.filter(inventory_quantity=0, track_inventory=True).count()
    low_stock = products.filter(
        inventory_quantity__lte=F('low_stock_threshold'),
        track_inventory=True
    ).count()
    
    # Top performing products
    top_products = products.annotate(
        order_count=Count('orderitem'),
        avg_rating=Avg('product_reviews__rating')
    ).order_by('-order_count')[:5]
    
    # Category distribution
    category_stats = products.values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    return Response({
        'statistics': {
            'total_products': total_products,
            'active_products': active_products,
            'out_of_stock': out_of_stock,
            'low_stock': low_stock,
        },
        'top_products': VendorProductListSerializer(top_products, many=True).data,
        'category_distribution': list(category_stats),
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_update_product_status(request):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    product_ids = request.data.get('product_ids', [])
    new_status = request.data.get('status')
    
    if not product_ids or not new_status:
        return Response({'error': 'product_ids and status are required'}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    updated_count = Product.objects.filter(
        id__in=product_ids,
        vendor=request.user
    ).update(status=new_status)
    
    return Response({
        'message': f'Updated {updated_count} products',
        'updated_count': updated_count
    })

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'customer', 'vendor', 'payment_status']
    search_fields = ['order_number', 'pickup_address', 'delivery_address', 'delivery_contact_name']
    ordering_fields = ['created_at', 'estimated_delivery_time', 'total_amount']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter based on user type
        if user.user_type == 'customer':
            queryset = queryset.filter(customer=user)
        elif user.user_type == 'vendor':
            queryset = queryset.filter(vendor=user)
        elif user.user_type == 'delivery_person':
            # Show orders assigned to this driver
            queryset = queryset.filter(dispatch__driver=user)
        elif user.user_type == 'dispatcher':
            # Dispatchers can see all orders
            pass
        
        return queryset

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(Order.STATUS_CHOICES):
            return Response(
                {'error': 'Invalid status'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = new_status
        order.save()
        
        serializer = self.get_serializer(order)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """Get orders for the current user based on their role"""
        user = request.user
        
        if user.user_type == 'customer':
            orders = Order.objects.filter(customer=user)
        elif user.user_type == 'vendor':
            orders = Order.objects.filter(vendor=user)
        elif user.user_type == 'delivery_person':
            orders = Order.objects.filter(dispatch__driver=user)
        else:
            orders = Order.objects.all()
        
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics for orders"""
        user = request.user
        
        if user.user_type == 'customer':
            orders = Order.objects.filter(customer=user)
        elif user.user_type == 'vendor':
            orders = Order.objects.filter(vendor=user)
        elif user.user_type == 'delivery_person':
            orders = Order.objects.filter(dispatch__driver=user)
        else:
            orders = Order.objects.all()
        
        stats = {
            'total_orders': orders.count(),
            'pending_orders': orders.filter(status='pending').count(),
            'in_progress_orders': orders.filter(
                status__in=['confirmed', 'preparing', 'assigned', 'picked_up', 'in_transit']
            ).count(),
            'completed_orders': orders.filter(status='delivered').count(),
            'cancelled_orders': orders.filter(status__in=['cancelled', 'failed']).count(),
        }
        
        return Response(stats)


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['order']
