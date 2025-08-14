from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/tracking/order/(?P<order_id>\w+)/$', consumers.OrderTrackingConsumer.as_asgi()),
    re_path(r'ws/tracking/driver/$', consumers.DriverLocationConsumer.as_asgi()),
]
