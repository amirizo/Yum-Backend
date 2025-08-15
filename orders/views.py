from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum
from .models import Category, Product, DeliveryAddress, Order, OrderItem, OrderStatusHistory
from .serializers import (
    CategorySerializer, ProductSerializer, DeliveryAddressSerializer,
    OrderCreateSerializer, OrderSerializer, OrderStatusHistorySerializer,
    OrderStatusUpdateSerializer
)

User = get_user_model()

# Category Views
class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category_type']

# Product Views
class ProductListView(generics.ListAPIView):
    queryset = Product.objects.filter(is_available=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'vendor', 'category__category_type']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_available=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

class VendorProductListView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_available', 'category__category_type']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'stock_quantity']
    ordering = ['-created_at']

    def get_queryset(self):
        return Product.objects.filter(vendor=self.request.user)

class VendorProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(vendor=self.request.user)

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

    def perform_create(self, serializer):
        serializer.save()

class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'vendor']
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

class OrderStatusHistoryView(generics.ListAPIView):
    serializer_class = OrderStatusHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        order_id = self.kwargs['order_id']
        return OrderStatusHistory.objects.filter(order_id=order_id)

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
    total_spent = orders.filter(status='delivered').aggregate(total=Sum('total_amount'))['total'] or 0
    
    return Response({
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'total_spent': float(total_spent),
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
    
    total_orders = orders.count()
    pending_orders = orders.filter(status__in=['pending', 'confirmed']).count()
    total_products = products.count()
    low_stock_products = products.filter(stock_quantity__lt=5).count()
    out_of_stock_products = products.filter(stock_quantity=0).count()
    
    return Response({
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
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
        
        return Response({'message': 'Order assigned successfully'})
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or not available'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def vendor_accept_order(request, order_id):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Only vendors can accept orders'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(id=order_id, vendor=request.user, status='pending')
        order.status = 'confirmed'
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='confirmed',
            changed_by=request.user,
            notes='Order accepted by vendor'
        )
        
        return Response({'message': 'Order accepted successfully'})
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be accepted'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def vendor_reject_order(request, order_id):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Only vendors can reject orders'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(id=order_id, vendor=request.user, status='pending')
        order.status = 'cancelled'
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='cancelled',
            changed_by=request.user,
            notes='Order rejected by vendor'
        )
        
        return Response({'message': 'Order rejected successfully'})
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be rejected'}, status=status.HTTP_404_NOT_FOUND)
