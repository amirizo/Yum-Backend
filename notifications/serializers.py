from rest_framework import serializers
from .models import Notification, NotificationPreference, PushNotificationDevice, RealTimeUpdate
from authentication.serializers import UserSerializer


class NotificationSerializer(serializers.ModelSerializer):
    sender_details = UserSerializer(source='sender', read_only=True)
    content_object_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'sender', 'sender_details', 'title', 'message',
            'notification_type', 'priority', 'is_read', 'read_at', 'created_at',
            'extra_data', 'content_object_data'
        ]
        read_only_fields = ['id', 'created_at', 'read_at']

    def get_content_object_data(self, obj):
        if obj.content_object:
            if hasattr(obj.content_object, 'order_number'):  # Order
                return {
                    'type': 'order',
                    'id': str(obj.content_object.id),
                    'order_number': obj.content_object.order_number,
                    'status': obj.content_object.status
                }
            elif hasattr(obj.content_object, 'driver'):  # Dispatch
                return {
                    'type': 'dispatch',
                    'id': str(obj.content_object.id),
                    'status': obj.content_object.status,
                    'driver_name': obj.content_object.driver.get_full_name()
                }
        return None


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'push_enabled', 'email_enabled', 'sms_enabled', 'websocket_enabled',
            'order_updates', 'delivery_updates', 'payment_updates', 'promotional',
            'system_alerts', 'quiet_hours_enabled', 'quiet_start_time', 'quiet_end_time'
        ]


class PushNotificationDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushNotificationDevice
        fields = ['id', 'device_token', 'device_type', 'device_name', 'is_active']
        read_only_fields = ['id']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class RealTimeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealTimeUpdate
        fields = [
            'id', 'update_type', 'order_id', 'dispatch_id', 'user_id',
            'data', 'timestamp', 'is_delivered', 'delivered_at'
        ]
        read_only_fields = ['id', 'timestamp']


class NotificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'recipient', 'title', 'message', 'notification_type', 'priority',
            'content_type', 'object_id', 'extra_data'
        ]

    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)
