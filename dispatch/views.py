from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count, Avg
from .models import Dispatch, DispatchRoute, DispatchStatusHistory
from .serializers import (
    DispatchSerializer, DispatchCreateSerializer, DispatchRouteSerializer,
    DispatchStatusHistorySerializer, LocationUpdateSerializer, StatusUpdateSerializer
)
from orders.models import Order


class DispatchViewSet(viewsets.ModelViewSet):
    queryset = Dispatch.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'driver', 'dispatcher', 'route']
    search_fields = ['order__order_number', 'driver__first_name', 'driver__last_name']
    ordering_fields = ['assigned_at', 'accepted_at']
    ordering = ['-assigned_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return DispatchCreateSerializer
        return DispatchSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter based on user type
        if user.user_type == 'delivery_person':
            queryset = queryset.filter(driver=user)
        elif user.user_type == 'dispatcher':
            # Dispatchers can see dispatches they created or all if admin
            if not user.is_staff:
                queryset = queryset.filter(dispatcher=user)
        
        return queryset

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        dispatch = self.get_object()
        serializer = StatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')
            latitude = serializer.validated_data.get('latitude')
            longitude = serializer.validated_data.get('longitude')
            
            # Update dispatch status
            dispatch.status = new_status
            
            # Update location if provided
            if latitude and longitude:
                dispatch.current_latitude = latitude
                dispatch.current_longitude = longitude
                dispatch.last_location_update = timezone.now()
            
            # Update timestamp fields based on status
            now = timezone.now()
            if new_status == 'accepted':
                dispatch.accepted_at = now
            elif new_status == 'en_route_pickup':
                dispatch.en_route_pickup_at = now
            elif new_status == 'arrived_pickup':
                dispatch.arrived_pickup_at = now
            elif new_status == 'picked_up':
                dispatch.picked_up_at = now
                dispatch.order.status = 'picked_up'
                dispatch.order.actual_pickup_time = now
            elif new_status == 'en_route_delivery':
                dispatch.en_route_delivery_at = now
                dispatch.order.status = 'in_transit'
            elif new_status == 'arrived_delivery':
                dispatch.arrived_delivery_at = now
            elif new_status == 'delivered':
                dispatch.delivered_at = now
                dispatch.order.status = 'delivered'
                dispatch.order.actual_delivery_time = now
            
            dispatch.save()
            dispatch.order.save()
            
            # Create status history entry
            DispatchStatusHistory.objects.create(
                dispatch=dispatch,
                status=new_status,
                location_latitude=latitude,
                location_longitude=longitude,
                notes=notes,
                created_by=request.user
            )
            
            return Response({'message': 'Status updated successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_location(self, request, pk=None):
        dispatch = self.get_object()
        serializer = LocationUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            dispatch.current_latitude = serializer.validated_data['latitude']
            dispatch.current_longitude = serializer.validated_data['longitude']
            dispatch.last_location_update = timezone.now()
            dispatch.save()
            
            return Response({'message': 'Location updated successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def available_orders(self, request):
        """Get orders available for dispatch assignment"""
        available_orders = Order.objects.filter(
            status__in=['confirmed', 'ready_for_pickup'],
            dispatch__isnull=True
        ).order_by('priority', 'created_at')
        
        from orders.serializers import OrderSerializer
        serializer = OrderSerializer(available_orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_dispatches(self, request):
        """Get dispatches for the current driver"""
        if request.user.user_type != 'delivery_person':
            return Response(
                {'error': 'Only delivery personnel can access this endpoint'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        dispatches = Dispatch.objects.filter(driver=request.user)
        serializer = self.get_serializer(dispatches, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics for dispatches"""
        user = request.user
        
        if user.user_type == 'delivery_person':
            dispatches = Dispatch.objects.filter(driver=user)
        elif user.user_type == 'dispatcher':
            dispatches = Dispatch.objects.filter(dispatcher=user)
        else:
            dispatches = Dispatch.objects.all()
        
        stats = {
            'total_dispatches': dispatches.count(),
            'active_dispatches': dispatches.filter(
                status__in=['assigned', 'accepted', 'en_route_pickup', 'picked_up', 'en_route_delivery']
            ).count(),
            'completed_dispatches': dispatches.filter(status='delivered').count(),
            'failed_dispatches': dispatches.filter(status__in=['failed', 'cancelled']).count(),
            'average_rating': dispatches.filter(customer_rating__isnull=False).aggregate(
                avg_rating=Avg('customer_rating')
            )['avg_rating'] or 0,
        }
        
        return Response(stats)


class DispatchRouteViewSet(viewsets.ModelViewSet):
    queryset = DispatchRoute.objects.all()
    serializer_class = DispatchRouteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'driver', 'dispatcher']
    search_fields = ['route_name', 'driver__first_name', 'driver__last_name']
    ordering_fields = ['created_at', 'total_distance', 'estimated_duration']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.user_type == 'delivery_person':
            queryset = queryset.filter(driver=user)
        elif user.user_type == 'dispatcher':
            if not user.is_staff:
                queryset = queryset.filter(dispatcher=user)
        
        return queryset

    @action(detail=True, methods=['patch'])
    def start_route(self, request, pk=None):
        route = self.get_object()
        route.status = 'active'
        route.started_at = timezone.now()
        route.save()
        
        # Update all dispatches in this route to active
        route.dispatches.update(status='accepted')
        
        return Response({'message': 'Route started successfully'})

    @action(detail=True, methods=['patch'])
    def complete_route(self, request, pk=None):
        route = self.get_object()
        route.status = 'completed'
        route.completed_at = timezone.now()
        
        # Calculate actual duration
        if route.started_at:
            duration = (route.completed_at - route.started_at).total_seconds() / 60
            route.actual_duration = int(duration)
        
        route.save()
        
        return Response({'message': 'Route completed successfully'})


class DispatchStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DispatchStatusHistory.objects.all()
    serializer_class = DispatchStatusHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['dispatch', 'status', 'created_by']
    ordering = ['-timestamp']
