from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Avg
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal
from geopy.distance import geodesic
import googlemaps
import json
import logging
from .models import Category, Product, DeliveryAddress, Order,  OrderItem, OrderStatusHistory, Cart, CartItem, calculate_delivery_fee
from .serializers import (
    CategorySerializer, ProductSerializer,ProductVariantSerializer,
    DeliveryAddressSerializer,
    OrderCreateSerializer, OrderSerializer, OrderStatusHistorySerializer,
    OrderStatusUpdateSerializer, CartSerializer, CartItemSerializer, 
    VendorWithProductsSerializer,CheckoutSerializer, VendorCategorySerializer
)
from rest_framework.exceptions import PermissionDenied
from .services import OrderNotificationService
from authentication.models import Vendor

User = get_user_model()
from .utils import add_item_to_cart, get_cart_for_request, remove_cart_item ,update_cart_item , clear_cart

logger = logging.getLogger(__name__)
# Category Views
class CategoryListView(generics.ListAPIView):
    """Public view to list all active categories"""
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category_type', 'vendor']

    def get_queryset(self):
        # Show both global categories (vendor=None) and vendor-specific categories
        return Category.objects.filter(is_active=True)


class VendorCategoryListCreateView(generics.ListCreateAPIView):
    """Vendor view to list their categories and create new ones"""
    serializer_class = VendorCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access this endpoint")
        return Category.objects.filter(vendor=self.request.user.vendor_profile)

    def perform_create(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can create categories")
        serializer.save()


class VendorCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vendor view to retrieve, update, or delete their categories"""
    serializer_class = VendorCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access this endpoint")
        return Category.objects.filter(vendor=self.request.user.vendor_profile)

    def perform_update(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can update categories")
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can delete categories")
        
        # Check if category has products
        if instance.products.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Cannot delete category that has products. Please remove or reassign products first.")
        
        instance.delete()


class VendorCategoryStatsView(generics.RetrieveAPIView):
    """Get statistics for vendor's categories"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access this endpoint")
        
        vendor = request.user.vendor_profile
        categories = Category.objects.filter(vendor=vendor)
        
        stats = {
            'total_categories': categories.count(),
            'active_categories': categories.filter(is_active=True).count(),
            'inactive_categories': categories.filter(is_active=False).count(),
            'categories_by_type': {
                'food': categories.filter(category_type='food').count(),
                'grocery': categories.filter(category_type='grocery').count(),
            },
            'categories_with_products': categories.filter(products__isnull=False).distinct().count(),
            'empty_categories': categories.filter(products__isnull=True).count(),
        }
        
        return Response(stats)

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
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access this endpoint")
        return Product.objects.filter(vendor=self.request.user.vendor_profile)

    def perform_create(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can create products")
        serializer.save(vendor=self.request.user.vendor_profile)



class VendorProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only vendors can access their products
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access this endpoint")
        return Product.objects.filter(vendor=self.request.user.vendor_profile)





class VendorRestaurantView(generics.RetrieveAPIView):
    """View for customers to see vendor restaurant page with business info and products"""
    serializer_class = VendorWithProductsSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    lookup_url_kwarg = 'vendor_id'
    
    def get_queryset(self):
        return User.objects.filter(user_type='vendor', is_active=True)
    
    def get_object(self):
        vendor_id = self.kwargs.get('vendor_id')
        try:
            vendor = User.objects.get(id=vendor_id, user_type='vendor', is_active=True)
            return vendor
        except User.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Vendor not found")




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

    def update(self, request, *args, **kwargs):
        """Allow partial updates without requiring all fields"""
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)



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
            return Order.objects.filter(vendor=user.vendor_profile)
        elif user.user_type == 'driver':
            return Order.objects.filter(driver=user.driver_profile)
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
            return Order.objects.filter(vendor=user.vendor_profile)
        elif user.user_type == 'driver':
            return Order.objects.filter(driver=user.driver_profile)
        else:
            return Order.objects.all()

class OrderStatusUpdateView(generics.UpdateAPIView):
    serializer_class = OrderStatusUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'vendor':
            return Order.objects.filter(vendor=user.vendor_profile)
        elif user.user_type == 'driver':
            return Order.objects.filter(driver=user.driver_profile)
        else:
            return Order.objects.all()

class OrderStatusHistoryView(generics.ListAPIView):
    serializer_class = OrderStatusHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        order_id = self.kwargs['order_id']
        return OrderStatusHistory.objects.filter(order_id=order_id)





class VendorOrdersView(APIView):
    def get(self, request):
        # Get orders for the authenticated vendor only
        vendor_orders = Order.objects.filter(vendor=request.user.vendor_profile)
        serializer = OrderSerializer(vendor_orders, many=True)
        return Response(serializer.data)


# Cart Management Views

# Cart Management Views


# class CartView(generics.RetrieveAPIView):
#     """Get user's current cart"""
#     serializer_class = CartSerializer
#     permission_classes = [permissions.AllowAny]
    
#     def get_object(self):
#         # For anonymous users, return empty cart data
#         if not self.request.user.is_authenticated:
#             return {'items': [], 'total_amount': 0, 'total_items': 0}
#         cart, created = Cart.objects.get_or_create(user=self.request.user)
#         return cart

# class AddToCartView(generics.CreateAPIView):
#     """Add item to cart"""
#     serializer_class = CartItemSerializer
#     permission_classes = [permissions.AllowAny]
    
#     def perform_create(self, serializer):
#         # For anonymous users, store in session
#         if not self.request.user.is_authenticated:
#             # Store cart in session for anonymous users
#             cart_data = self.request.session.get('cart', [])
#             product_id = serializer.validated_data['product_id']
#             quantity = serializer.validated_data.get('quantity', 1)
            
#             # Check if item already exists
#             for item in cart_data:
#                 if item['product_id'] == product_id:
#                     item['quantity'] += quantity
#                     break
#             else:
#                 cart_data.append({
#                     'product_id': product_id,
#                     'quantity': quantity,
#                     'special_instructions': serializer.validated_data.get('special_instructions', '')
#                 })
            
#             self.request.session['cart'] = cart_data
#             return
        
#         cart, created = Cart.objects.get_or_create(user=self.request.user)
        
#         # Check if item already exists in cart
#         product_id = serializer.validated_data['product_id']
#         try:
#             cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
#             # Update quantity if item exists
#             cart_item.quantity += serializer.validated_data.get('quantity', 1)
#             cart_item.special_instructions = serializer.validated_data.get('special_instructions', cart_item.special_instructions)
#             cart_item.save()
#             return cart_item
#         except CartItem.DoesNotExist:
#             # Create new cart item
#             serializer.save(cart=cart)

# class UpdateCartItemView(generics.UpdateAPIView):
#     """Update cart item quantity or instructions"""
#     serializer_class = CartItemSerializer
#     permission_classes = [permissions.AllowAny]
    
#     def get_queryset(self):
#         if not self.request.user.is_authenticated:
#             return CartItem.objects.none()
#         return CartItem.objects.filter(cart__user=self.request.user)

# class RemoveFromCartView(generics.DestroyAPIView):
#     """Remove item from cart"""
#     permission_classes = [permissions.AllowAny]
    
#     def get_queryset(self):
#         if not self.request.user.is_authenticated:
#             return CartItem.objects.none()
#         return CartItem.objects.filter(cart__user=self.request.user)

# class ClearCartView(generics.GenericAPIView):
#     """Clear all items from cart"""
#     permission_classes = [permissions.AllowAny]
    
#     def delete(self, request):
#         if not request.user.is_authenticated:
#             request.session['cart'] = []
#             return Response({'message': 'Cart cleared successfully'}, status=status.HTTP_200_OK)
        
#         try:
#             cart = Cart.objects.get(user=request.user)
#             cart.items.all().delete()
#             cart.vendor = None
#             cart.save()
#             return Response({'message': 'Cart cleared successfully'}, status=status.HTTP_200_OK)
#         except Cart.DoesNotExist:
#             return Response({'message': 'Cart is already empty'}, status=status.HTTP_200_OK)



class CartView(generics.RetrieveAPIView):
    """Get current cart for user or guest"""
    serializer_class = CartSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        cart, cart_data, is_auth = get_cart_for_request(self.request)
        if is_auth:
            return cart
        return {
            "items": cart_data,
            "total_amount": sum(
                item['quantity'] * item_price(item['product_id'])
                for item in cart_data
            ),
            "total_items": sum(item['quantity'] for item in cart_data)
        }


def item_price(product_id):
    """Get price of a product without importing inside function repeatedly"""
    from .models import Product
    return Product.objects.get(id=product_id).price


class AddToCartView(generics.CreateAPIView):
    """Add product to cart"""
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        add_item_to_cart(
            request=self.request,
            product_id=serializer.validated_data['product_id'],
            quantity=serializer.validated_data.get('quantity', 1),
            special_instructions=serializer.validated_data.get('special_instructions', '')
        )


class UpdateCartItemView(generics.UpdateAPIView):
    """Update quantity or instructions of a cart item"""
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]
    queryset = CartItem.objects.all()

    def update(self, request, *args, **kwargs):
        product_id = int(kwargs.get('pk'))
        update_cart_item(
            request=request,
            product_id=product_id,
            quantity=request.data.get('quantity', 1),
            special_instructions=request.data.get('special_instructions', '')
        )
        return Response({"message": "Cart item updated"})


class RemoveFromCartView(generics.DestroyAPIView):
    """Remove product from cart"""
    permission_classes = [permissions.AllowAny]
    queryset = CartItem.objects.all()

    def destroy(self, request, *args, **kwargs):
        product_id = int(kwargs.get('pk'))
        remove_cart_item(request, product_id)
        return Response({"message": "Cart item removed"})


class ClearCartView(generics.GenericAPIView):
    """Clear all cart items"""
    permission_classes = [permissions.AllowAny]

    def delete(self, request):
        clear_cart(request)
        return Response({"message": "Cart cleared"})

class CheckoutView(generics.CreateAPIView):
    """Calculate checkout totals and preview order (doesn't create order)"""
    permission_classes = [permissions.AllowAny]
    serializer_class = CheckoutSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vendor_id = serializer.validated_data["vendor_id"]
        delivery_address = serializer.validated_data["delivery_address"]

        # Fetch vendor (ensure it's active)
        try:
            vendor = Vendor.objects.get(id=vendor_id, status="active")
        except Vendor.DoesNotExist:
            return Response(
                {"error": f"Vendor with id {vendor_id} does not exist or is inactive"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Ensure vendor has a primary location
        if not vendor.primary_location:
            return Response(
                {"error": "Vendor does not have a primary location set"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get cart
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user, vendor=vendor).first()
        else:
            cart_id = serializer.validated_data.get("cart_id")
            cart = Cart.objects.filter(id=cart_id, vendor=vendor).first()

        if not cart or not cart.items.exists():
            return Response(
                {"error": "Cart is empty"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate totals
        cart_total = cart.get_total_amount()

        vendor_coords = (
            float(vendor.primary_location.latitude),
            float(vendor.primary_location.longitude)
        )
        customer_coords = (
            float(delivery_address["latitude"]),
            float(delivery_address["longitude"])
        )
        distance_km = geodesic(vendor_coords, customer_coords).km
        fee_per_km = Decimal("2000")  # 2000 TZS per km
        delivery_fee = (Decimal(distance_km) * fee_per_km).quantize(Decimal("0.01"))

        grand_total = cart_total + delivery_fee

        return Response({
            "vendor": vendor.business_name,
            "cart_total": f"{cart_total} TZS",
            "delivery_fee": f"{delivery_fee} TZS",
            "grand_total": f"{grand_total} TZS",
            "distance_km": round(distance_km, 2),
            "delivery_from": vendor.primary_location.address,
            "delivery_to": delivery_address,
            "message": "Use /api/payments/create-order-and-payment/ to create the order and process payment"
        })



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
    orders = Order.objects.filter(vendor=user.vendor_profile)
    products = Product.objects.filter(vendor=user.vendor_profile)
    
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
        
        # Check if driver is available
        driver_profile = getattr(request.user, 'driver_profile', None)
        if not driver_profile or not driver_profile.is_available:
            return Response({'error': 'Driver is not available for deliveries'}, status=status.HTTP_400_BAD_REQUEST)
        
        order.driver = request.user.driver_profile
        order.status = 'picked_up'
        order.save()  # This will trigger the comprehensive notification system through signals
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='picked_up',
            changed_by=request.user,
            notes='Order picked up by driver'
        )
        OrderNotificationService.send_order_picked_up_email(order)
        return Response({
            'message': 'Order assigned successfully',
            'order_number': order.order_number,
            'status': order.status
        })
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or not available'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def vendor_set_preparing(request, order_id):
    """Vendor sets order status to preparing"""
    if request.user.user_type != 'vendor':
        return Response({'error': 'Only vendors can update order status'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(
            id=order_id,
            vendor=request.user.vendor_profile,
            status='confirmed',
            payment_status='paid'
        )
        
        old_status = order.status
        order.status = 'preparing'
        order.save()  # This will trigger the notification system through signals
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='preparing',
            changed_by=request.user,
            notes='Vendor started preparing the order'
        )

        OrderNotificationService.send_order_status_update_email(order)
        
        return Response({
            'message': 'Order status updated to preparing',
            'order_number': order.order_number,
            'status': order.status
        })
        
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be updated'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def vendor_set_ready(request, order_id):
    """Vendor sets order status to ready and notifies drivers"""
    if request.user.user_type != 'vendor':
        return Response({'error': 'Only vendors can update order status'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(
            id=order_id,
            vendor=request.user.vendor_profile,
            status='preparing',
            payment_status='paid'
        )
        
        old_status = order.status
        order.status = 'ready'
        
        # Set estimated delivery time if not already set
        if not order.estimated_delivery_time:
            order.estimated_delivery_time = timezone.now() + timezone.timedelta(minutes=30)
        
        order.save()  # This will trigger the comprehensive notification system through signals
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='ready',
            changed_by=request.user,
            notes='Order is ready for pickup'
        )
        OrderNotificationService.notify_all_drivers_new_order(order)
        return Response({
            'message': 'Order is ready for pickup. Drivers have been notified.',
            'order_number': order.order_number,
            'status': order.status,
            'estimated_delivery': order.estimated_delivery_time
        })
        
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be updated'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def driver_mark_delivered(request, order_id):
    """Driver marks order as delivered"""
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can mark orders as delivered'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(
            id=order_id,
            driver=request.user.driver_profile,
            status__in=['picked_up', 'in_transit']
        )
        
        old_status = order.status
        order.status = 'delivered'
        order.actual_delivery_time = timezone.now()
        order.delivered_at = timezone.now()
        order.save()  # This will trigger the comprehensive notification system through signals
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='delivered',
            changed_by=request.user,
            notes='Order delivered to customer'
        )
        
        OrderNotificationService.send_order_delivered_email(order)
        OrderNotificationService.notify_vendor_order_delivered(order)
        # Update driver availability if needed
        driver_profile = request.user.driver_profile
        driver_profile.total_deliveries += 1
        driver_profile.save()
        
        return Response({
            'message': 'Order marked as delivered successfully',
            'order_number': order.order_number,
            'status': order.status,
            'delivery_time': order.actual_delivery_time
        })
        
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be marked as delivered'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def driver_update_location(request, order_id):
    """Driver updates their location during delivery"""
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can update location'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(
            id=order_id,
            driver=request.user.driver_profile,
            status__in=['picked_up', 'in_transit']
        )
        
        
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not latitude or not longitude:
            return Response({'error': 'Latitude and longitude are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update driver's current location
        driver_profile = request.user.driver_profile
        driver_profile.current_latitude = latitude
        driver_profile.current_longitude = longitude
        driver_profile.last_location_update = timezone.now()
        driver_profile.save()
        

        # Update order status to in_transit if not already
        if order.status != 'in_transit':
            old_status = order.status
            order.status = 'in_transit'
            order.save()  # This will trigger the comprehensive notification system through signals
            
            # Create status history
            OrderStatusHistory.objects.create(
                order=order,
                status='in_transit',
                changed_by=request.user,
                notes='Driver is en route to delivery location'
            )
        
        # Send real-time location update via WebSocket
        from notifications.services import NotificationService
        NotificationService.send_driver_location_update(order, latitude, longitude, driver_profile)
        
        return Response({
            'message': 'Location updated successfully',
            'order_status': order.status,
            'latitude': float(latitude),
            'longitude': float(longitude)
        })
        
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def available_orders_for_drivers(request):
    """Get list of orders available for driver pickup"""
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can access this endpoint'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get orders that are ready and don't have a driver assigned
    orders = Order.objects.filter(
        status='ready',
        driver__isnull=True,
        payment_status='paid'
    ).select_related('vendor', 'customer').prefetch_related('items__product')
    
    # Calculate distance from driver's location if available
    driver_profile = request.user.driver_profile
    order_data = []
    
    for order in orders:
        vendor_location = order.vendor.primary_location
        order_info = {
            'id': str(order.id),
            'order_number': order.order_number,
            'vendor_name': order.vendor.business_name,
            'vendor_address': vendor_location.address if vendor_location else 'N/A',
            'customer_address': order.delivery_address_text,
            'total_amount': order.total_amount,
            'item_count': order.items.count(),
            'estimated_delivery_time': order.estimated_delivery_time,
            'created_at': order.created_at,
        }
        
        # Calculate distance if driver location is available
        if (driver_profile.current_latitude and driver_profile.current_longitude and 
            vendor_location and vendor_location.latitude and vendor_location.longitude):
            
            distance = calculate_delivery_fee(
                float(driver_profile.current_latitude),
                float(driver_profile.current_longitude),
                float(vendor_location.latitude),
                float(vendor_location.longitude)
            )
            order_info['distance_km'] = distance
        
        order_data.append(order_info)
    
    # Sort by distance if available, otherwise by creation time
    if any('distance_km' in order for order in order_data):
        order_data.sort(key=lambda x: x.get('distance_km', float('inf')))
    else:
        order_data.sort(key=lambda x: x['created_at'], reverse=True)
    
    return Response({
        'available_orders': order_data,
        'count': len(order_data)
    })



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def vendor_accept_order(request, order_id):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Only vendors can accept orders'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(
            id=order_id, 
            vendor=request.user.vendor_profile, 
            status='pending',
            payment_status='paid'
        )
        order.status = 'confirmed'
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='confirmed',
            changed_by=request.user,
            notes='Order accepted by vendor'
        )

        # Send email notification to customer
        OrderNotificationService.send_order_accepted_email(order)
        
        return Response({'message': 'Order accepted successfully'})
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be accepted'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def vendor_reject_order(request, order_id):
    if request.user.user_type != 'vendor':
        return Response({'error': 'Only vendors can reject orders'}, status=status.HTTP_403_FORBIDDEN)

    rejection_reason = request.data.get('reason', 'No reason provided')
    
    try:
        order = Order.objects.get(id=order_id, 
            vendor=request.user.vendor_profile,
            status='pending',
            payment_status='paid'
        )
        order.status = 'cancelled'
        order.save()
        
        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            status='cancelled',
            changed_by=request.user,
            notes='Order rejected by vendor'
        )

        # Send customer refund notification
        OrderNotificationService.send_order_rejected_email(order, rejection_reason)
        
        # Send admin notification with customer contact info
        OrderNotificationService.send_order_rejection_admin_email(order, rejection_reason)
        
        return Response({'message': 'Order rejected successfully'})
    except Order.DoesNotExist:
        return Response({'error': 'Order not found or cannot be rejected'}, status=status.HTTP_404_NOT_FOUND)




@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def calculate_delivery_fee_api(request):
    """Calculate delivery fee based on customer and vendor coordinates"""
    try:
        customer_lat = request.data.get('customer_latitude')
        customer_lng = request.data.get('customer_longitude')
        vendor_id = request.data.get('vendor_id')

        if not all([customer_lat, customer_lng, vendor_id]):
            return Response(
                {'error': 'Customer coordinates and vendor ID are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get vendor
        try:
            vendor = User.objects.get(id=vendor_id, user_type='vendor').vendor_profile
        except User.DoesNotExist:
            return Response({'error': 'Vendor not found'}, status=status.HTTP_404_NOT_FOUND)

        # Get vendor's primary location
        primary_location = vendor.locations.filter(is_primary=True).first()
        if not primary_location:
            return Response({'error': 'Vendor location not available'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate delivery fee
        delivery_fee = calculate_delivery_fee(
            float(customer_lat),
            float(customer_lng),
            float(primary_location.latitude),
            float(primary_location.longitude)
        )

        return Response({
            'delivery_fee': delivery_fee,
            'vendor_name': vendor.business_name,
            'vendor_address': primary_location.address
        })

    except Exception as e:
        return Response(
            {'error': f'Error calculating delivery fee: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def geocode_address(request):
    """Convert address to coordinates using Google Maps API"""
    try:
        address = request.data.get('address')
        if not address:
            return Response({'error': 'Address is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not settings.GOOGLE_MAPS_API_KEY:
            return Response({'error': 'Google Maps API key not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        geocode_result = gmaps.geocode(address, region='TZ')  # Restrict to Tanzania
        
        if not geocode_result:
            return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)
        
        place = geocode_result[0]
        location = place['geometry']['location']

        return Response({
            'latitude': location['lat'],
            'longitude': location['lng'],
            'formatted_address': place.get('formatted_address', ''),
            'place_id': place.get('place_id', '')
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': f'Error geocoding address: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def reverse_geocode(request):
    """Convert coordinates to address using Google Maps API"""
    try:
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not latitude or not longitude:
            return Response({
                'error': 'Latitude and longitude are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not settings.GOOGLE_MAPS_API_KEY:
            return Response({
                'error': 'Google Maps API key not configured'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Initialize Google Maps client
        gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        
        # Reverse geocode the coordinates
        reverse_geocode_result = gmaps.reverse_geocode((latitude, longitude))
        
        if not reverse_geocode_result:
            return Response({
                'error': 'Location not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        formatted_address = reverse_geocode_result[0]['formatted_address']
        
        return Response({
            'formatted_address': formatted_address,
            'place_id': reverse_geocode_result[0].get('place_id', ''),
            'address_components': reverse_geocode_result[0].get('address_components', [])
        })
        
    except Exception as e:
        return Response({
            'error': f'Error reverse geocoding: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Payment-related functionality has been moved to the payments app

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def driver_deliveries(request):
    """Get all deliveries for the authenticated driver"""
    if request.user.user_type != 'driver':
        return Response({'error': 'Only drivers can access this endpoint'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        driver_profile = request.user.driver_profile
        
        # Get filter parameters from query params
        status_filter = request.GET.get('status', None)  # Filter by order status
        date_from = request.GET.get('date_from', None)  # Filter from date (YYYY-MM-DD)
        date_to = request.GET.get('date_to', None)      # Filter to date (YYYY-MM-DD)
        page = int(request.GET.get('page', 1))          # Pagination
        page_size = int(request.GET.get('page_size', 20))  # Items per page
        
        # Base queryset - all orders assigned to this driver
        deliveries = Order.objects.filter(
            driver=driver_profile
        ).select_related(
            'customer', 'vendor', 'vendor__user'
        ).prefetch_related(
            'items__product', 'status_history'
        ).order_by('-created_at')
        
        # Apply status filter if provided
        if status_filter:
            valid_statuses = ['picked_up', 'in_transit', 'delivered', 'cancelled']
            if status_filter in valid_statuses:
                deliveries = deliveries.filter(status=status_filter)
            else:
                return Response({
                    'error': f'Invalid status. Valid options: {", ".join(valid_statuses)}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Apply date filters if provided
        if date_from:
            try:
                from datetime import datetime
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                deliveries = deliveries.filter(created_at__date__gte=date_from_obj)
            except ValueError:
                return Response({
                    'error': 'Invalid date_from format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if date_to:
            try:
                from datetime import datetime
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                deliveries = deliveries.filter(created_at__date__lte=date_to_obj)
            except ValueError:
                return Response({
                    'error': 'Invalid date_to format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate pagination
        total_count = deliveries.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_deliveries = deliveries[start_index:end_index]
        
        # Build response data
        delivery_data = []
        for order in paginated_deliveries:
            # Calculate delivery details
            pickup_address = order.vendor.primary_location.address if order.vendor.primary_location else 'N/A'
            delivery_address = order.delivery_address_text
            
            # Get order items summary
            items_summary = []
            for item in order.items.all():
                items_summary.append({
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'price': item.total_price,
                    'special_instructions': item.special_instructions or 'None'
                })
            
            # Calculate delivery earnings (you can adjust this logic based on your commission structure)
            delivery_earnings = order.delivery_fee * Decimal('0.8')  # Driver gets 80% of delivery fee
            
            delivery_info = {
                'id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
                'customer_info': {
                    'name': f"{order.customer.first_name} {order.customer.last_name}",
                    'phone': order.customer.phone_number,
                    'email': order.customer.email
                },
                'vendor_info': {
                    'name': order.vendor.business_name,
                    'phone': order.vendor.user.phone_number
                },
                'addresses': {
                    'pickup_address': pickup_address,
                    'delivery_address': delivery_address,
                    'delivery_latitude': order.delivery_latitude,
                    'delivery_longitude': order.delivery_longitude
                },
                'order_details': {
                    'items': items_summary,
                    'total_amount': order.total_amount,
                    'delivery_fee': order.delivery_fee,
                    'item_count': order.items.count()
                },
                'earnings': {
                    'delivery_earnings': delivery_earnings,
                    'currency': 'TZS'
                },
                'timestamps': {
                    'ordered_at': order.created_at,
                    'picked_up_at': order.status_history.filter(status='picked_up').first().timestamp if order.status_history.filter(status='picked_up').exists() else None,
                    'delivered_at': order.actual_delivery_time,
                    'estimated_delivery': order.estimated_delivery_time
                },
                'payment_status': order.payment_status,
                'special_instructions': order.special_instructions or 'None'
            }
            
            delivery_data.append(delivery_info)
        
        # Calculate statistics
        all_driver_orders = Order.objects.filter(driver=driver_profile)
        stats = {
            'total_deliveries': all_driver_orders.filter(status='delivered').count(),
            'active_deliveries': all_driver_orders.filter(status__in=['picked_up', 'in_transit']).count(),
            'total_earnings': float(all_driver_orders.filter(status='delivered').aggregate(
                total=Sum('delivery_fee')
            )['total'] or 0) * 0.8,  # Driver gets 80%
            'completion_rate': 0
        }
        
        # Calculate completion rate
        total_assigned = all_driver_orders.count()
        if total_assigned > 0:
            completed = all_driver_orders.filter(status='delivered').count()
            stats['completion_rate'] = round((completed / total_assigned) * 100, 2)
        
        # Pagination info
        total_pages = (total_count + page_size - 1) // page_size
        pagination_info = {
            'current_page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1
        }
        
        return Response({
            'deliveries': delivery_data,
            'statistics': stats,
            'pagination': pagination_info,
            'filters_applied': {
                'status': status_filter,
                'date_from': date_from,
                'date_to': date_to
            }
        })
        
    except Exception as e:
        logger.error(f"Error retrieving driver deliveries: {str(e)}")
        return Response({
            'error': 'An error occurred while retrieving deliveries'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)