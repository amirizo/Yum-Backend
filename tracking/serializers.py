from rest_framework import serializers
from .models import (
    DriverLocation, OrderTracking, LiveTracking, 
    TrackingEvent, Geofence, NotificationQueue
)
from authentication.serializers import UserSerializer, DriverProfileSerializer
from orders.serializers import OrderSerializer

class DriverLocationSerializer(serializers.ModelSerializer):
    driver = DriverProfileSerializer(read_only=True)

    class Meta:
        model = DriverLocation
        fields = '__all__'

class LocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8)
    accuracy = serializers.FloatField(default=0)
    speed = serializers.FloatField(required=False, allow_null=True)
    heading = serializers.FloatField(required=False, allow_null=True)
    altitude = serializers.FloatField(required=False, allow_null=True)

class OrderTrackingSerializer(serializers.ModelSerializer):
    updated_by = UserSerializer(read_only=True)

    class Meta:
        model = OrderTracking
        fields = '__all__'

class LiveTrackingSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    driver = DriverProfileSerializer(read_only=True)

    class Meta:
        model = LiveTracking
        fields = '__all__'

class TrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEvent
        fields = '__all__'

class GeofenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Geofence
        fields = '__all__'

class NotificationQueueSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)

    class Meta:
        model = NotificationQueue
        fields = '__all__'

class OrderTrackingDetailSerializer(serializers.Serializer):
    """Comprehensive order tracking information"""
    order = OrderSerializer(read_only=True)
    current_status = serializers.CharField()
    tracking_updates = OrderTrackingSerializer(many=True, read_only=True)
    live_tracking = LiveTrackingSerializer(read_only=True)
    estimated_arrival = serializers.DateTimeField(required=False, allow_null=True)
    driver_location = serializers.SerializerMethodField()

    def get_driver_location(self, obj):
        if hasattr(obj, 'driver') and obj.driver:
            latest_location = DriverLocation.objects.filter(
                driver=obj.driver
            ).first()
            if latest_location:
                return DriverLocationSerializer(latest_location).data
        return None
