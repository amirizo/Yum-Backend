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
from payments.models import PayoutRequest, Refund, Payment
from .serializers import (
    CategorySerializer, ProductSerializer,ProductVariantSerializer,
    DeliveryAddressSerializer,
    OrderCreateSerializer, OrderSerializer, OrderStatusHistorySerializer,
    OrderStatusUpdateSerializer, CartSerializer, CartItemSerializer, 
    VendorWithProductsSerializer,CheckoutSerializer, VendorCategorySerializer
)
from rest_framework.exceptions import PermissionDenied, ValidationError
from .services import OrderNotificationService
from authentication.models import Vendor
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .utils import add_item_to_cart, get_cart_for_request, remove_cart_item ,update_cart_item , clear_cart

User = get_user_model()
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
    parser_classes = [MultiPartParser, FormParser]  # ✅ Add this

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
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # ✅ Include JSON parser pia

    def get_queryset(self):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access this endpoint")
        return Category.objects.filter(vendor=self.request.user.vendor_profile)

    def perform_update(self, serializer):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can update categories")
        # ✅ partial update (PATCH) ili usilazimishe kuweka field zote
        serializer.save(partial=True)

    def update(self, request, *args, **kwargs):
        """Override ili PATCH/PUT zote ziwe partial update"""
        kwargs['partial'] = True  # ✅ Force partial update
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can delete categories")
        
        # Check if category has products
        if instance.products.exists():
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

    parser_classes = [MultiPartParser, FormParser]  # <-- important

    def get_queryset(self):
        """Restrict to vendor's own products"""
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can access this endpoint")
        return Product.objects.filter(vendor=self.request.user.vendor_profile)

    def update(self, request, *args, **kwargs):
        """Allow partial updates without overwriting missing fields"""
        kwargs['partial'] = True  # ✅ ensures PATCH-like behavior
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """Extra permission check before saving"""
        if self.request.user.user_type != 'vendor':
            raise PermissionDenied("Only vendors can update products")
        serializer.save(vendor=self.request.user.vendor_profile)





class VendorRestaurantView(generics.RetrieveAPIView):
    """View for customers to see vendor restaurant page with business info and products"""
    serializer_class = VendorWithProductsSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    lookup_url_kwarg = 'vendor_id'
    
    def get_queryset(self):
        return Vendor.objects.filter(user__user_type='vendor', user__is_active=True)
    
    def get_object(self):
        vendor_id = self.kwargs.get('vendor_id')
        try:
            return Vendor.objects.get(id=vendor_id, user__user_type='vendor', user__is_active=True)
        except Vendor.DoesNotExist:
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





# class VendorOrdersView(APIView):
#     def get(self, request):
#         # Get orders for the authenticated vendor only
#         vendor_orders = Order.objects.filter(vendor=request.user.vendor_profile)
#         serializer = OrderSerializer(vendor_orders, many=True)
#         return Response(serializer.data)


class VendorOrdersView(APIView):
    def get(self, request):
        # Hakikisha vendor yupo
        vendor = getattr(request.user, "vendor_profile", None)
        if not vendor:
            return Response({"detail": "Vendor profile not found"}, status=404)

        # Chukua orders ambazo zipo kwa huyu vendor na zimeshalipiwa
        vendor_orders = Order.objects.filter(
            vendor=vendor,
            payment_status="paid"
        ).order_by("-created_at")  # unaweza kuweka order kwa tarehe mpya kwanza

        serializer = OrderSerializer(vendor_orders, many=True)
        return Response(serializer.data, status=200)

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

    def create(self, request, *args, **kwargs):
        # Validate incoming data first
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Perform add/update
        self.perform_create(serializer)

        # Fetch updated cart representation
        cart, cart_data, is_auth = get_cart_for_request(request)
        if is_auth:
            # Use CartSerializer for authenticated users
            cart = cart  # already obtained from get_cart_for_request
            data = CartSerializer(cart, context={'request': request}).data
        else:
            # Anonymous: construct payload similar to CartView
            total_amount = sum(
                item['quantity'] * item_price(item['product_id'])
                for item in cart_data
            ) if cart_data else 0
            total_items = sum(item['quantity'] for item in (cart_data or []))
            data = {
                'items': cart_data or [],
                'total_amount': total_amount,
                'total_items': total_items
            }

        headers = self.get_success_headers(serializer.data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)


# class UpdateCartItemView(generics.UpdateAPIView):
#     """Update quantity or instructions of a cart item"""
#     serializer_class = CartItemSerializer
#     permission_classes = [permissions.AllowAny]
#     queryset = CartItem.objects.all()

#     def update(self, request, *args, **kwargs):
#         product_id = int(kwargs.get('pk'))
#         update_cart_item(
#             request=request,
#             product_id=product_id,
#             quantity=request.data.get('quantity', 1),
#             special_instructions=request.data.get('special_instructions', '')
#         )

#         # Return updated cart payload
#         cart, cart_data, is_auth = get_cart_for_request(request)
#         if is_auth:
#             data = CartSerializer(cart, context={'request': request}).data
#         else:
#             total_amount = sum(
#                 item['quantity'] * item_price(item['product_id'])
#                 for item in cart_data
#             ) if cart_data else 0
#             total_items = sum(item['quantity'] for item in (cart_data or []))
#             data = {
#                 'items': cart_data or [],
#                 'total_amount': total_amount,
#                 'total_items': total_items
#             }

#         return Response(data)


# class RemoveFromCartView(generics.DestroyAPIView):
#     """Remove product from cart"""
#     permission_classes = [permissions.AllowAny]
#     queryset = CartItem.objects.all()

#     def destroy(self, request, *args, **kwargs):
#         product_id = int(kwargs.get('pk'))
#         remove_cart_item(request, product_id)
#         return Response({"message": "Cart item removed"})


# ---------------------------
# Update item (quantity or notes)
# ---------------------------
# class UpdateCartItemView(generics.UpdateAPIView):
#     serializer_class = CartItemSerializer
#     permission_classes = [permissions.AllowAny]
#     queryset = CartItem.objects.all()

#     def update(self, request, *args, **kwargs):
#         instance = self.get_object()
#         quantity = request.data.get("quantity")
#         special_instructions = request.data.get("special_instructions")

#         if quantity is not None:
#             instance.quantity = int(quantity)
#         if special_instructions is not None:
#             instance.special_instructions = special_instructions

#         instance.save()
#         return Response(CartItemSerializer(instance).data, status=status.HTTP_200_OK)


# class UpdateCartItemView(generics.UpdateAPIView):
#     serializer_class = CartItemSerializer
#     permission_classes = [permissions.AllowAny]
#     queryset = CartItem.objects.all()

#     def update(self, request, *args, **kwargs):
#         instance = self.get_object()
#         quantity = request.data.get("quantity")
#         special_instructions = request.data.get("special_instructions")

#         if quantity is not None:
#             instance.quantity = int(quantity)
#         if special_instructions is not None:
#             instance.special_instructions = special_instructions

#         instance.save()

#         # ✅ Pass request into context so image returns as full URL
#         serializer = CartItemSerializer(instance, context={'request': request})
#         return Response(serializer.data, status=status.HTTP_200_OK)


# # ---------------------------
# # Remove item
# # ---------------------------
# class RemoveFromCartView(generics.DestroyAPIView):
#     permission_classes = [permissions.AllowAny]
#     queryset = CartItem.objects.all()

#     def destroy(self, request, *args, **kwargs):
#         instance = self.get_object()
#         instance.delete()
#         return Response({"detail": "Item removed"}, status=status.HTTP_204_NO_CONTENT)





# class ClearCartView(generics.GenericAPIView):
#     """Clear all cart items"""
#     permission_classes = [permissions.AllowAny]

#     def delete(self, request):
#         clear_cart(request)
#         return Response({"message": "Cart cleared"})



class UpdateCartItemView(generics.UpdateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.AllowAny]
    queryset = CartItem.objects.all()

    def update(self, request, *args, **kwargs):
        # For authenticated users - update CartItem directly
        if request.user.is_authenticated:
            instance = self.get_object()
            quantity = request.data.get("quantity")
            special_instructions = request.data.get("special_instructions")

            if quantity is not None:
                quantity = int(quantity)
                if quantity <= 0:
                    # Remove item if quantity is 0 or negative
                    cart = instance.cart
                    instance.delete()
                    
                    # Clear cart vendor if no items remain
                    if not cart.items.exists():
                        cart.vendor = None
                        cart.save()
                else:
                    instance.quantity = quantity
                    
            if special_instructions is not None:
                instance.special_instructions = special_instructions
                
            if quantity > 0:
                instance.save()

            # Return updated cart data
            cart, cart_data, is_auth = get_cart_for_request(request)
            return Response(
                CartSerializer(cart, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        else:
            # For anonymous users - update session cart
            product_id = int(kwargs.get('pk'))
            quantity = request.data.get("quantity")
            special_instructions = request.data.get("special_instructions")
            
            cart_data = request.session.get('cart', [])
            
            # Find and update the item
            for item in cart_data:
                if item.get('product_id') == product_id:
                    if quantity is not None:
                        quantity = int(quantity)
                        if quantity <= 0:
                            # Remove item if quantity is 0 or negative
                            cart_data.remove(item)
                        else:
                            item['quantity'] = quantity
                    
                    if special_instructions is not None and quantity > 0:
                        item['special_instructions'] = special_instructions
                    break
            
            request.session['cart'] = cart_data
            request.session.modified = True
            
            # Return updated cart data for anonymous users
            total_amount = sum(
                item['quantity'] * item_price(item['product_id'])
                for item in cart_data
            ) if cart_data else 0
            total_items = sum(item['quantity'] for item in cart_data) if cart_data else 0
            
            return Response({
                'items': cart_data,
                'total_amount': total_amount,
                'total_items': total_items
            }, status=status.HTTP_200_OK)


class RemoveFromCartView(generics.DestroyAPIView):
    permission_classes = [permissions.AllowAny]
    queryset = CartItem.objects.all()

    def destroy(self, request, *args, **kwargs):
        # For authenticated users
        if request.user.is_authenticated:
            instance = self.get_object()
            cart = instance.cart
            instance.delete()
            
            # Clear cart vendor if no items remain
            if not cart.items.exists():
                cart.vendor = None
                cart.save()
            
            # Return updated cart data
            cart, cart_data, is_auth = get_cart_for_request(request)
            return Response(
                CartSerializer(cart, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        else:
            # For anonymous users - remove from session cart
            product_id = int(kwargs.get('pk'))
            cart_data = request.session.get('cart', [])
            
            # Find and remove the item
            cart_data = [item for item in cart_data if item.get('product_id') != product_id]
            
            request.session['cart'] = cart_data
            request.session.modified = True
            
            # Return updated cart data for anonymous users
            total_amount = sum(
                item['quantity'] * item_price(item['product_id'])
                for item in cart_data
            ) if cart_data else 0
            total_items = sum(item['quantity'] for item in cart_data) if cart_data else 0
            
            return Response({
                'items': cart_data,
                'total_amount': total_amount,
                'total_items': total_items,
                'message': 'Item removed from cart'
            }, status=status.HTTP_200_OK)


class ClearCartView(generics.GenericAPIView):
    """Clear all cart items"""
    permission_classes = [permissions.AllowAny]

    def delete(self, request):
        if request.user.is_authenticated:
            # Clear authenticated user's cart
            try:
                cart = Cart.objects.get(user=request.user)
                cart.items.all().delete()
                cart.vendor = None
                cart.save()
            except Cart.DoesNotExist:
                pass
            
            # Return empty cart data
            cart, cart_data, is_auth = get_cart_for_request(request)
            return Response(
                CartSerializer(cart, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        else:
            # Clear anonymous user's session cart
            request.session['cart'] = []
            request.session.modified = True
            
            return Response({
                'items': [],
                'total_amount': 0,
                'total_items': 0,
                'message': 'Cart cleared successfully'
            }, status=status.HTTP_200_OK)

# ...existing code...

# class CheckoutView(generics.CreateAPIView):
#     """Calculate checkout totals and preview order with complete validation"""
#     permission_classes = [permissions.IsAuthenticated]
    
#     def get_serializer_class(self):
#         from .checkout_serializers import CheckoutValidationSerializer
#         return CheckoutValidationSerializer

#     def post(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data, context={'request': request})
#         serializer.is_valid(raise_exception=True)

#         vendor_id = serializer.validated_data["vendor_id"]
#         delivery_address_data = serializer.validated_data["delivery_address"]
#         payment_method_data = serializer.validated_data["payment_method"]
#         special_instructions = serializer.validated_data.get("special_instructions", "")
#         save_address = serializer.validated_data.get("save_address", False)
#         address_label = serializer.validated_data.get("address_label", "")

#         # Get vendor
#         vendor = Vendor.objects.get(id=vendor_id, status="active")
#         vendor_location = vendor.primary_location

#         # Get cart items and calculate totals
#         cart_items = []
#         cart_total = Decimal('0.00')
#         items_count = 0
        
#         if request.user.is_authenticated:
#             cart = Cart.objects.filter(user=request.user, vendor=vendor).first()
#             if cart and cart.items.exists():
#                 for cart_item in cart.items.all():
#                     item_data = {
#                         'product_id': cart_item.product.id,
#                         'product_name': cart_item.product.name,
#                         'product_price': cart_item.product.price,
#                         'quantity': cart_item.quantity,
#                         'total_price': cart_item.total_price,
#                         'special_instructions': cart_item.special_instructions
#                     }
#                     cart_items.append(item_data)
#                     cart_total += cart_item.total_price
#                     items_count += cart_item.quantity
#         else:
#             # Handle anonymous cart from session
#             session_cart = request.session.get('cart', [])
            
#             for item in session_cart:
#                 try:
#                     product = Product.objects.get(id=item['product_id'], is_available=True)
#                     if product.vendor_id == vendor_id:
#                         item_total = product.price * Decimal(str(item['quantity']))
#                         item_data = {
#                             'product_id': product.id,
#                             'product_name': product.name,
#                             'product_price': product.price,
#                             'quantity': item['quantity'],
#                             'total_price': item_total,
#                             'special_instructions': item.get('special_instructions', '')
#                         }
#                         cart_items.append(item_data)
#                         cart_total += item_total
#                         items_count += item['quantity']
#                 except Product.DoesNotExist:
#                     continue

#         if cart_total == 0:
#             return Response(
#                 {"error": "Cart is empty or contains no items from this vendor"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         # Validate minimum order amount
#         if cart_total < vendor.minimum_order_amount:
#             return Response({
#                 "error": f"Minimum order amount is {vendor.minimum_order_amount} TSH. Current total: {cart_total} TSH"
#             }, status=status.HTTP_400_BAD_REQUEST)

#         # Calculate delivery fee using existing function
#         delivery_fee = Decimal(str(calculate_delivery_fee(
#             float(delivery_address_data["latitude"]),
#             float(delivery_address_data["longitude"]),
#             float(vendor_location.latitude),
#             float(vendor_location.longitude)
#         )))

#         # Calculate distance for display
#         from geopy.distance import geodesic
#         distance_km = geodesic(
#             (float(vendor_location.latitude), float(vendor_location.longitude)),
#             (float(delivery_address_data["latitude"]), float(delivery_address_data["longitude"]))
#         ).km

#         # Calculate tax (if applicable)
#         tax_rate = Decimal('0.00')  # Set your tax rate here
#         tax_amount = (cart_total * tax_rate).quantize(Decimal("0.01"))
        
#         # Calculate total
#         total_amount = cart_total + delivery_fee + tax_amount

#         # Estimate delivery time (base time + distance factor)
#         base_prep_time = vendor.average_preparation_time
#         delivery_time_per_km = 3  # 3 minutes per km
#         estimated_delivery_time = base_prep_time + int(distance_km * delivery_time_per_km)

#         # Determine delivery calculation method
#         if distance_km <= 3:
#             delivery_calculation = f"≤3km rate: {distance_km:.2f}km × 2000 TSH = {delivery_fee} TSH"
#         else:
#             delivery_calculation = f"≥4km rate: {distance_km:.2f}km × 700 TSH = {delivery_fee} TSH"

#         # Get accepted payment methods
#         payment_methods = []
#         if vendor.accepts_mobile_money:
#             payment_methods.append('mobile_money')
#         if vendor.accepts_card:
#             payment_methods.append('card')
#         if vendor.accepts_cash:
#             payment_methods.append('cash')

#         # Save address if requested and user is authenticated
#         saved_address_id = None
#         if save_address and request.user.is_authenticated and address_label:
#             try:
#                 from .models import DeliveryAddress
#                 address = DeliveryAddress.objects.create(
#                     user=request.user,
#                     label=address_label,
#                     street_address=delivery_address_data['address'],
#                     city=delivery_address_data.get('city', ''),
#                     state=delivery_address_data.get('state', ''),
                   
#                     latitude=delivery_address_data['latitude'],
#                     longitude=delivery_address_data['longitude'],
#                     formatted_address=delivery_address_data['address']
#                 )
#                 saved_address_id = address.id
#             except Exception as e:
#                 # Don't fail checkout if address saving fails
#                 pass

#         # Prepare response
#         response_data = {
#             "checkout_id": f"CHK_{vendor_id}_{int(timezone.now().timestamp())}",
#             "vendor": {
#                 "id": vendor.id,
#                 "name": vendor.business_name,
#                 "address": vendor_location.address,
#                 "phone": vendor.business_phone,
#                 "minimum_order_amount": vendor.minimum_order_amount
#             },
#             "cart_items": cart_items,
#             "pricing": {
#                 "subtotal": cart_total,
#                 "delivery_fee": delivery_fee,
#                 "tax_amount": tax_amount,
#                 "total_amount": total_amount,
#                 "currency": "TSH"
#             },
#             "delivery_info": {
#                 "distance_km": round(distance_km, 2),
#                 "estimated_delivery_time": estimated_delivery_time,
#                 "delivery_calculation": delivery_calculation,
#                 "address": delivery_address_data
#             },
#             "payment_info": {
#                 "selected_method": payment_method_data,
#                 "accepted_methods": payment_methods
#             },
#             "order_summary": {
#                 "items_count": items_count,
#                 "special_instructions": special_instructions,
#                 "saved_address_id": saved_address_id
#             },
#             "validation": {
#                 "can_proceed": True,
#                 "message": "Checkout validation successful. Ready to proceed with payment."
#             }
#         }

#         return Response(response_data, status=status.HTTP_200_OK)



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
    orders = Order.objects.filter(vendor=user.vendor_profile, payment_status='paid')
    payout_requests = PayoutRequest.objects.filter(vendor=user.vendor_profile)
    products = Product.objects.filter(vendor=user.vendor_profile,)
    
    total_orders = orders.count()
    pending_orders = orders.filter(status__in=['pending', 'confirmed'], payment_status='paid').count()
    completed_orders = orders.filter(status='delivered').count()  # ✅ paid + delivered
    total_products = products.count()
    
    low_stock_products = products.filter(stock_quantity__lt=5).count()
    out_of_stock_products = products.filter(stock_quantity=0).count()


    # Revenue
    revenue = orders.filter(status='delivered').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    pending_payouts = payout_requests.filter(status='pending').aggregate(
        total=Sum('amount')
    )['total'] or 0

    active_orders = orders.filter(
        status__in=['confirmed', 'preparing', 'ready', 'picked_up', 'in_transit']
    ).count()  # actively being processed

    return Response({
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'total_products': total_products,
        'revenue': revenue, 
        'active_orders': active_orders, 
        'pending_payouts': float(pending_payouts),
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

       
        OrderNotificationService.send_order_status_update_email(order, old_status, order.status)
        
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
        
        # old_status = order.status
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
        
        # old_status = order.status
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

# Customer Order Management Views
class CustomerOrderHistoryView(generics.ListAPIView):
    """List a customer's past orders (order history)."""
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Only customers should see their own history; vendors/drivers/admins can use other endpoints
        if user.user_type == 'customer':
            qs = Order.objects.filter(customer=user, payment_status='paid').order_by('-created_at')
        else:
            qs = Order.objects.filter(customer=user, payment_status='paid')  # fallback

        # optional filters
        status = self.request.query_params.get('status')
        payment_status = self.request.query_params.get('payment_status')
        if status:
            qs = qs.filter(status=status)
        if payment_status:
            qs = qs.filter(payment_status=payment_status)
        return qs


class CancelOrderView(APIView):
    """Allow customers to request cancellation of an order.
    - Customers can cancel orders that are in 'pending' or 'confirmed' state before preparation/pickup.
    - If payment exists and succeeded, a Refund object will be created in pending state.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        # Only allow cancellation if order not yet in progress
        if order.status in ('preparing', 'ready', 'picked_up', 'in_transit', 'delivered'):
            return Response({'error': 'Order cannot be cancelled at this stage'}, status=status.HTTP_400_BAD_REQUEST)

        # Mark order cancelled
        order.status = 'cancelled'
        order.save()

        # If a successful payment exists, create refund request
        payment = getattr(order, 'payment', None)
        if payment and payment.status == 'succeeded':
            try:
                refund = Refund.objects.create(
                    payment=payment,
                    amount=payment.amount,
                    currency=payment.currency,
                    reason='order_canceled',
                    status='pending'
                )
                # Notify payments/admin for manual processing
                from notifications.services import NotificationService
                NotificationService.send_order_status_notification(order, old_status=None)
            except Exception as e:
                logger.exception('Failed to create refund for cancelled order %s: %s', order.order_number, e)

        # Notify vendor and customer
        try:
            OrderNotificationService.send_new_order_notification(order)
        except Exception:
            logger.exception('Failed to send cancellation notifications for order %s', order.order_number)

        return Response({'message': 'Order cancelled successfully'}, status=status.HTTP_200_OK)


class RequestRefundView(APIView):
    """Customer requests a refund for an order/payment. This creates a Refund record for admin processing."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        amount = request.data.get('amount')
        reason = request.data.get('reason', 'requested_by_customer')

        try:
            order = Order.objects.get(id=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        payment = getattr(order, 'payment', None)
        if not payment or payment.status != 'succeeded':
            return Response({'error': 'No eligible payment found for refund'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_val = Decimal(amount) if amount else payment.amount
        except Exception:
            return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            refund = Refund.objects.create(
                payment=payment,
                amount=amount_val,
                currency=payment.currency,
                reason=reason,
                status='pending'
            )
            # Notify admin/payments team
            try:
                from notifications.services import NotificationService
                NotificationService.send_order_status_notification(order, old_status=None)
            except Exception:
                logger.exception('Failed to notify about refund request for order %s', order.order_number)

            return Response({'message': 'Refund request created', 'refund_id': str(refund.id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception('Failed to create refund request for order %s: %s', order.order_number, e)
            return Response({'error': 'Failed to create refund request'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReorderFromOrderView(APIView):
    """Add all items from a past order back into the customer's cart. Use replace=true to overwrite existing cart."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        replace = str(request.query_params.get('replace', 'true')).lower() in ('1', 'true', 'yes')
        try:
            order = Order.objects.get(id=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        # If replace, clear current cart
        if replace:
            try:
                clear_cart(request)
            except Exception:
                logger.exception('Failed to clear cart for reorder for user %s', request.user.id)

        # Add items to cart using helper which supports authenticated users
        added = []
        for item in order.items.all():
            try:
                add_item_to_cart(request, product_id=item.product.id, quantity=item.quantity, special_instructions=item.special_instructions or '')
                added.append({'product_id': item.product.id, 'quantity': item.quantity})
            except Exception:
                logger.exception('Failed adding product %s to cart for reorder', getattr(item.product, 'id', None))

        return Response({'message': 'Order items added to cart', 'items': added}, status=status.HTTP_200_OK)