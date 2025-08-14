from rest_framework import serializers
from .models import Dispatch, DispatchRoute, DispatchStatusHistory
from orders.serializers import OrderSerializer
from authentication.serializers import UserSerializer


class DispatchRouteSerializer(serializers.ModelSerializer):
    driver_details = UserSerializer(source='driver', read_only=True)
    dispatcher_details = UserSerializer(source='dispatcher', read_only=True)
    dispatches_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DispatchRoute
        fields = [
            'id', 'route_name', 'driver', 'dispatcher', 'driver_details', 'dispatcher_details',
            'total_distance', 'estimated_duration', 'actual_duration', 'status', 'created_at',
            'updated_at', 'started_at', 'completed_at', 'optimization_score', 'fuel_estimate',
            'dispatches_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_dispatches_count(self, obj):
        return obj.dispatches.count()


class DispatchStatusHistorySerializer(serializers.ModelSerializer):
    created_by_details = UserSerializer(source='created_by', read_only=True)
    
    class Meta:
        model = DispatchStatusHistory
        fields = [
            'id', 'status', 'timestamp', 'location_latitude', 'location_longitude',
            'notes', 'created_by', 'created_by_details'
        ]
        read_only_fields = ['id', 'timestamp']


class DispatchSerializer(serializers.ModelSerializer):
    order_details = OrderSerializer(source='order', read_only=True)
    driver_details = UserSerializer(source='driver', read_only=True)
    dispatcher_details = UserSerializer(source='dispatcher', read_only=True)
    route_details = DispatchRouteSerializer(source='route', read_only=True)
    status_history = DispatchStatusHistorySerializer(many=True, read_only=True)
    
    class Meta:
        model = Dispatch
        fields = [
            'id', 'order', 'driver', 'dispatcher', 'route', 'order_details', 'driver_details',
            'dispatcher_details', 'route_details', 'assigned_at', 'accepted_at', 'status',
            'current_latitude', 'current_longitude', 'last_location_update', 'distance_traveled',
            'time_to_pickup', 'time_to_delivery', 'driver_notes', 'customer_rating', 'customer_feedback',
            'en_route_pickup_at', 'arrived_pickup_at', 'picked_up_at', 'en_route_delivery_at',
            'arrived_delivery_at', 'delivered_at', 'status_history'
        ]
        read_only_fields = ['id', 'assigned_at']


class DispatchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispatch
        fields = ['order', 'driver', 'dispatcher', 'route']

    def create(self, validated_data):
        dispatch = super().create(validated_data)
        
        # Create initial status history
        DispatchStatusHistory.objects.create(
            dispatch=dispatch,
            status='assigned',
            created_by=validated_data['dispatcher'],
            notes='Order assigned to driver'
        )
        
        # Update order status
        dispatch.order.status = 'assigned'
        dispatch.order.save()
        
        return dispatch


class LocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8)


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Dispatch.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8, required=False)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8, required=False)
