from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationViewSet, NotificationPreferenceViewSet,
    PushNotificationDeviceViewSet, RealTimeUpdateViewSet
)

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'preferences', NotificationPreferenceViewSet, basename='notification-preference')
router.register(r'devices', PushNotificationDeviceViewSet, basename='push-device')
router.register(r'updates', RealTimeUpdateViewSet, basename='realtime-update')

urlpatterns = [
    path('api/', include(router.urls)),
]
