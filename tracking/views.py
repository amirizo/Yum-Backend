from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import (
    DriverLocation, OrderTracking, LiveTracking, 
    TrackingEvent, Geofence, NotificationQueue
)
from .serializers import (
    DriverLocationSerializer, LocationUpdateSerializer,
    OrderTrackingSerializer, LiveTrackingSerializer,
    OrderTrackingDetailSerializer, NotificationQueueSerializer
)
from .services import TrackingService
from orders.models import Order
from authentication.permissions import IsDriver, IsCustomer

class DriverLocationUpdateView(generics.CreateAPIView):
    serializer_class = LocationUpdateSerializer
    permission_classes = [IsDriver]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        tracking_service = TrackingService()
        location = tracking_service.update_driver_location(
            request.user.driver,
            serializer.validated_data['latitude'],
            serializer.validated_data['longitude'],
            serializer.validated_data.get('accuracy', 0),
            serializer.validated_data.get('speed'),
            serializer.validated_data.get('heading')
        )
        
        return Response({
            'message': 'Location updated successfully',
            'location_id': location.id
        }, status=status.HTTP_201_CREATED)

class DriverLocationHistoryView(generics.ListAPIView):
    serializer_class = DriverLocationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type == 'driver':
            return DriverLocation.objects.filter(driver__user=self.request.user)
        elif self.request.user.user_type == 'admin':
            driver_id = self.request.query_params.get('driver_id')
            if driver_id:
                return DriverLocation.objects.filter(driver_id=driver_id)
            return DriverLocation.objects.all()
        return DriverLocation.objects.none()

class OrderTrackingDetailView(generics.RetrieveAPIView):
    serializer_class = OrderTrackingDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        order_id = self.kwargs.get('order_id')
        order = get_object_or_404(Order, id=order_id)
        
        # Check permissions
        user = self.request.user
        if not (user == order.customer or 
                user == order.vendor.user or 
                (order.driver and user == order.driver.user) or
                user.user_type == 'admin'):
            raise permissions.PermissionDenied('You cannot track this order')
        
        return order

    def retrieve(self, request, *args, **kwargs):
        order = self.get_object()
        
        data = {
            'order': order,
            'current_status': order.status,
            'tracking_updates': order.tracking_updates.all()[:20],
            'live_tracking': getattr(order, 'live_tracking', None),
            'estimated_arrival': order.estimated_delivery_time
        }
        
        serializer = self.get_serializer(data)
        return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsDriver])
def start_delivery_tracking(request, order_id):
    """Start live tracking for a delivery"""
    try:
        order = Order.objects.get(id=order_id, driver__user=request.user)
        
        if order.status not in ['assigned', 'picked_up']:
            return Response({
                'error': 'Cannot start tracking for this order status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tracking_service = TrackingService()
        live_tracking = tracking_service.start_live_tracking(order)
        
        if live_tracking:
            return Response({
                'message': 'Live tracking started',
                'session_id': str(live_tracking.session_id)
            })
        else:
            return Response({
                'error': 'Failed to start live tracking'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found or not assigned to you'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsDriver])
def end_delivery_tracking(request, order_id):
    """End live tracking for a delivery"""
    try:
        order = Order.objects.get(id=order_id, driver__user=request.user)
        
        tracking_service = TrackingService()
        success = tracking_service.end_live_tracking(order)
        
        if success:
            return Response({'message': 'Live tracking ended'})
        else:
            return Response({
                'error': 'No active tracking session found'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found or not assigned to you'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsDriver])
def update_order_status(request, order_id):
    """Update order status from driver app"""
    try:
        order = Order.objects.get(id=order_id, driver__user=request.user)
        new_status = request.data.get('status')
        message = request.data.get('message', '')
        
        if not new_status:
            return Response({
                'error': 'Status is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate status transition
        valid_transitions = {
            'assigned': ['picked_up', 'cancelled'],
            'picked_up': ['in_transit', 'delivered'],
            'in_transit': ['delivered', 'failed']
        }
        
        if order.status not in valid_transitions or new_status not in valid_transitions[order.status]:
            return Response({
                'error': f'Invalid status transition from {order.status} to {new_status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tracking_service = TrackingService()
        tracking_service.update_order_status(order, new_status)
        
        # Create tracking record with location if provided
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        OrderTracking.objects.create(
            order=order,
            status=new_status,
            message=message,
            latitude=latitude,
            longitude=longitude,
            updated_by=request.user
        )
        
        return Response({'message': f'Order status updated to {new_status}'})
        
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found or not assigned to you'
        }, status=status.HTTP_404_NOT_FOUND)

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationQueueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return NotificationQueue.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')[:50]


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_nearby_drivers(request):
    """Get nearby available drivers (for admin/dispatch)"""
    if request.user.user_type != 'admin':
        return Response({
            'error': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    latitude = request.query_params.get('latitude')
    longitude = request.query_params.get('longitude')
    radius_km = float(request.query_params.get('radius', 10))
    
    if not latitude or not longitude:
        return Response({
            'error': 'Latitude and longitude are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    tracking_service = TrackingService()
    
    # Get all available drivers with location
    from authentication.models import Driver
    available_drivers = Driver.objects.filter(
        is_available=True,
        is_verified=True,
        is_online=True,
        current_latitude__isnull=False,
        current_longitude__isnull=False
    )
    
    nearby_drivers = []
    for driver in available_drivers:
        distance = tracking_service.calculate_distance(
            float(latitude), float(longitude),
            float(driver.current_latitude), float(driver.current_longitude)
        )
        
        if distance <= radius_km:
            nearby_drivers.append({
                'driver': {
                    'id': driver.id,
                    'username': driver.user.username,
                    'vehicle_type': driver.vehicle_type,
                    'rating': float(driver.rating),
                    'total_deliveries': driver.total_deliveries
                },
                'location': {
                    'latitude': float(driver.current_latitude),
                    'longitude': float(driver.current_longitude),
                    'last_update': driver.last_location_update.isoformat() if driver.last_location_update else None
                },
                'distance_km': round(distance, 2)
            })
    
    # Sort by distance
    nearby_drivers.sort(key=lambda x: x['distance_km'])
    
    return Response({
        'drivers': nearby_drivers,
        'total_count': len(nearby_drivers)
    })
