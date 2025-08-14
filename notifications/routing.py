from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/tracking/(?P<order_id>[0-9a-f-]+)/$', consumers.TrackingConsumer.as_asgi()),
]
