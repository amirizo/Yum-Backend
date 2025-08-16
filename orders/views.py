from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Avg
from .models import Category, Product, DeliveryAddress, Order,  OrderItem, OrderStatusHistory, Cart, CartItem, calculate_delivery_fee
from .serializers import (
    CategorySerializer, ProductSerializer,ProductVariantSerializer,
    DeliveryAddressSerializer,
    OrderCreateSerializer, OrderSerializer, OrderStatusHistorySerializer,
    OrderStatusUpdateSerializer, CartSerializer, CartItemSerializer, 
    VendorWithProductsSerializer,CheckoutSerializer
)
from rest_framework.exceptions import PermissionDenied
from .services import OrderNotificationService
from decimal import Decimal
from authentication.models import Vendor

User = get_user_model()
from django.shortcuts import get_object_or_404
from django.conf import settings
import googlemaps
from .utils import add_item_to_cart, get_cart_for_request, remove_cart_item ,update_cart_item , clear_cart
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
            "delivery_to": delivery_address
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