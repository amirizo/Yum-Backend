from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count
from .models import Notification, NotificationPreference, PushNotificationDevice, RealTimeUpdate
from .serializers import (
    NotificationSerializer, NotificationPreferenceSerializer,
    PushNotificationDeviceSerializer, RealTimeUpdateSerializer,
    NotificationCreateSerializer
)
from .services import NotificationService


class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'priority', 'is_read']
    search_fields = ['title', 'message']
    ordering_fields = ['created_at', 'priority']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=['patch'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'message': 'Notification marked as read'})

    @action(detail=False, methods=['patch'])
    def mark_all_as_read(self, request):
        count = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return Response({'message': f'{count} notifications marked as read'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).count()
        
        return Response({'unread_count': count})

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        user_notifications = Notification.objects.filter(recipient=request.user)
        
        stats = {
            'total_notifications': user_notifications.count(),
            'unread_notifications': user_notifications.filter(is_read=False).count(),
            'high_priority_unread': user_notifications.filter(
                is_read=False, priority__in=['high', 'urgent']
            ).count(),
            'notifications_by_type': dict(
                user_notifications.values('notification_type').annotate(
                    count=Count('id')
                ).values_list('notification_type', 'count')
            )
        }
        
        return Response(stats)

    @action(detail=False, methods=['post'])
    def send_notification(self, request):
        """Send notification to users (admin/dispatcher only)"""
        if not request.user.is_staff and request.user.user_type != 'dispatcher':
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = NotificationCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            notification = serializer.save()
            
            # Send via notification service
            NotificationService.send_notification(notification)
            
            return Response(
                NotificationSerializer(notification).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)

    def get_object(self):
        # Get or create preferences for the user
        preferences, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return preferences

    def list(self, request, *args, **kwargs):
        # Return user's preferences
        preferences = self.get_object()
        serializer = self.get_serializer(preferences)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        preferences = self.get_object()
        serializer = self.get_serializer(preferences, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PushNotificationDeviceViewSet(viewsets.ModelViewSet):
    serializer_class = PushNotificationDeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PushNotificationDevice.objects.filter(user=self.request.user)

    @action(detail=True, methods=['patch'])
    def deactivate(self, request, pk=None):
        device = self.get_object()
        device.is_active = False
        device.save()
        return Response({'message': 'Device deactivated'})


class RealTimeUpdateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RealTimeUpdateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['update_type', 'order_id', 'dispatch_id']
    ordering = ['-timestamp']

    def get_queryset(self):
        user = self.request.user
        queryset = RealTimeUpdate.objects.all()
        
        # Filter based on user access
        if user.user_type == 'customer':
            # Get orders for this customer
            from orders.models import Order
            user_orders = Order.objects.filter(customer=user).values_list('id', flat=True)
            queryset = queryset.filter(order_id__in=user_orders)
        elif user.user_type == 'vendor':
            from orders.models import Order
            user_orders = Order.objects.filter(vendor=user).values_list('id', flat=True)
            queryset = queryset.filter(order_id__in=user_orders)
        elif user.user_type == 'delivery_person':
            queryset = queryset.filter(user_id=user.id)
        # Dispatchers and admins can see all updates
        
        return queryset

    @action(detail=False, methods=['get'])
    def recent_updates(self, request):
        """Get recent updates for dashboard"""
        recent_updates = self.get_queryset()[:20]
        serializer = self.get_serializer(recent_updates, many=True)
        return Response(serializer.data)
