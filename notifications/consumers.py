import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from .models import RealTimeUpdate
from orders.models import Order
from dispatch.models import Dispatch

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        if self.user == AnonymousUser():
            await self.close()
            return
        
        # Create user-specific group
        self.user_group_name = f"user_{self.user.id}"
        
        # Join user group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        # Join role-based groups
        if self.user.user_type == 'delivery_person':
            self.driver_group_name = f"drivers"
            await self.channel_layer.group_add(
                self.driver_group_name,
                self.channel_name
            )
        elif self.user.user_type == 'dispatcher':
            self.dispatcher_group_name = f"dispatchers"
            await self.channel_layer.group_add(
                self.dispatcher_group_name,
                self.channel_name
            )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to notification service',
            'user_id': self.user.id,
            'user_type': self.user.user_type
        }))

    async def disconnect(self, close_code):
        # Leave user group
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
        
        # Leave role-based groups
        if hasattr(self, 'driver_group_name'):
            await self.channel_layer.group_discard(
                self.driver_group_name,
                self.channel_name
            )
        if hasattr(self, 'dispatcher_group_name'):
            await self.channel_layer.group_discard(
                self.dispatcher_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'location_update':
                await self.handle_location_update(text_data_json)
            elif message_type == 'status_update':
                await self.handle_status_update(text_data_json)
            elif message_type == 'join_order_room':
                await self.join_order_room(text_data_json)
            elif message_type == 'leave_order_room':
                await self.leave_order_room(text_data_json)
            
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))

    async def handle_location_update(self, data):
        """Handle real-time location updates from drivers"""
        if self.user.user_type != 'delivery_person':
            return
        
        dispatch_id = data.get('dispatch_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if dispatch_id and latitude and longitude:
            # Update dispatch location in database
            await self.update_dispatch_location(dispatch_id, latitude, longitude)
            
            # Broadcast location update to order room
            order_id = await self.get_order_id_from_dispatch(dispatch_id)
            if order_id:
                await self.channel_layer.group_send(
                    f"order_{order_id}",
                    {
                        'type': 'location_update',
                        'dispatch_id': dispatch_id,
                        'latitude': latitude,
                        'longitude': longitude,
                        'timestamp': data.get('timestamp')
                    }
                )

    async def handle_status_update(self, data):
        """Handle status updates"""
        dispatch_id = data.get('dispatch_id')
        status = data.get('status')
        
        if dispatch_id and status:
            # Update status in database
            await self.update_dispatch_status(dispatch_id, status)
            
            # Broadcast status update
            order_id = await self.get_order_id_from_dispatch(dispatch_id)
            if order_id:
                await self.channel_layer.group_send(
                    f"order_{order_id}",
                    {
                        'type': 'status_update',
                        'dispatch_id': dispatch_id,
                        'status': status,
                        'timestamp': data.get('timestamp')
                    }
                )

    async def join_order_room(self, data):
        """Join order-specific room for real-time updates"""
        order_id = data.get('order_id')
        if order_id:
            # Verify user has access to this order
            has_access = await self.verify_order_access(order_id)
            if has_access:
                await self.channel_layer.group_add(
                    f"order_{order_id}",
                    self.channel_name
                )
                await self.send(text_data=json.dumps({
                    'type': 'joined_order_room',
                    'order_id': order_id
                }))

    async def leave_order_room(self, data):
        """Leave order-specific room"""
        order_id = data.get('order_id')
        if order_id:
            await self.channel_layer.group_discard(
                f"order_{order_id}",
                self.channel_name
            )

    # WebSocket message handlers
    async def notification_message(self, event):
        """Send notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))

    async def location_update(self, event):
        """Send location update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'dispatch_id': event['dispatch_id'],
            'latitude': event['latitude'],
            'longitude': event['longitude'],
            'timestamp': event['timestamp']
        }))

    async def status_update(self, event):
        """Send status update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'dispatch_id': event['dispatch_id'],
            'status': event['status'],
            'timestamp': event['timestamp']
        }))

    async def order_update(self, event):
        """Send order update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'order_update',
            'order_id': event['order_id'],
            'status': event['status'],
            'data': event.get('data', {})
        }))

    # Database operations
    @database_sync_to_async
    def update_dispatch_location(self, dispatch_id, latitude, longitude):
        try:
            from django.utils import timezone
            dispatch = Dispatch.objects.get(id=dispatch_id, driver=self.user)
            dispatch.current_latitude = latitude
            dispatch.current_longitude = longitude
            dispatch.last_location_update = timezone.now()
            dispatch.save()
            
            # Create real-time update record
            RealTimeUpdate.objects.create(
                update_type='location',
                dispatch_id=dispatch_id,
                order_id=dispatch.order.id,
                user_id=self.user.id,
                data={
                    'latitude': str(latitude),
                    'longitude': str(longitude)
                }
            )
            return True
        except Dispatch.DoesNotExist:
            return False

    @database_sync_to_async
    def update_dispatch_status(self, dispatch_id, status):
        try:
            dispatch = Dispatch.objects.get(id=dispatch_id)
            dispatch.status = status
            dispatch.save()
            
            # Create real-time update record
            RealTimeUpdate.objects.create(
                update_type='status',
                dispatch_id=dispatch_id,
                order_id=dispatch.order.id,
                user_id=self.user.id,
                data={'status': status}
            )
            return True
        except Dispatch.DoesNotExist:
            return False

    @database_sync_to_async
    def get_order_id_from_dispatch(self, dispatch_id):
        try:
            dispatch = Dispatch.objects.get(id=dispatch_id)
            return str(dispatch.order.id)
        except Dispatch.DoesNotExist:
            return None

    @database_sync_to_async
    def verify_order_access(self, order_id):
        try:
            order = Order.objects.get(id=order_id)
            # Check if user has access to this order
            if self.user.user_type == 'customer':
                return order.customer == self.user
            elif self.user.user_type == 'vendor':
                return order.vendor == self.user
            elif self.user.user_type == 'delivery_person':
                return hasattr(order, 'dispatch') and order.dispatch.driver == self.user
            elif self.user.user_type in ['dispatcher', 'admin']:
                return True
            return False
        except Order.DoesNotExist:
            return False


class TrackingConsumer(AsyncWebsocketConsumer):
    """Dedicated consumer for real-time tracking"""
    
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.user = self.scope["user"]
        
        if self.user == AnonymousUser():
            await self.close()
            return
        
        # Verify access to order
        has_access = await self.verify_order_access(self.order_id)
        if not has_access:
            await self.close()
            return
        
        self.room_group_name = f'tracking_{self.order_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current tracking data
        tracking_data = await self.get_current_tracking_data(self.order_id)
        await self.send(text_data=json.dumps({
            'type': 'tracking_data',
            'data': tracking_data
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def tracking_update(self, event):
        """Send tracking update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'tracking_update',
            'data': event['data']
        }))

    @database_sync_to_async
    def verify_order_access(self, order_id):
        try:
            order = Order.objects.get(id=order_id)
            if self.user.user_type == 'customer':
                return order.customer == self.user
            elif self.user.user_type == 'vendor':
                return order.vendor == self.user
            elif self.user.user_type == 'delivery_person':
                return hasattr(order, 'dispatch') and order.dispatch.driver == self.user
            elif self.user.user_type in ['dispatcher', 'admin']:
                return True
            return False
        except Order.DoesNotExist:
            return False

    @database_sync_to_async
    def get_current_tracking_data(self, order_id):
        try:
            order = Order.objects.get(id=order_id)
            data = {
                'order_id': str(order.id),
                'status': order.status,
                'estimated_delivery_time': order.estimated_delivery_time.isoformat() if order.estimated_delivery_time else None,
            }
            
            if hasattr(order, 'dispatch'):
                dispatch = order.dispatch
                data.update({
                    'dispatch_id': str(dispatch.id),
                    'driver_name': dispatch.driver.get_full_name(),
                    'current_latitude': str(dispatch.current_latitude) if dispatch.current_latitude else None,
                    'current_longitude': str(dispatch.current_longitude) if dispatch.current_longitude else None,
                    'last_location_update': dispatch.last_location_update.isoformat() if dispatch.last_location_update else None,
                })
            
            return data
        except Order.DoesNotExist:
            return {}
