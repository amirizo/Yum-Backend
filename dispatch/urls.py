from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DispatchViewSet, DispatchRouteViewSet, DispatchStatusHistoryViewSet

router = DefaultRouter()
router.register(r'dispatches', DispatchViewSet)
router.register(r'routes', DispatchRouteViewSet)
router.register(r'status-history', DispatchStatusHistoryViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
