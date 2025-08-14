import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from authentication.models import User
from orders.models import Order
from .models import LiveTracking, DriverLocation, OrderTracking

class OrderTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.order_group_name = f'order_{self.order_id}'
        
        # Check if user has permission to track this order
        user = self.scope["user"]
        if isinstance(user, AnonymousUser):
            await self.close()
            return
        
        has_permission = await self.check_tracking_permission(user, self.order_id)
        if not has_permission:
            await self.close()
            return

        # Join order group
        await self.channel_layer.group_add(
            self.order_group_name,
            self.channel_name
        )

        await self.accept()

        # Send current order status
        order_data = await self.get_order_tracking_data(self.order_id)
        await self.send(text_data=json.dumps({
            'type': 'order_status',
            'data': order_data
        }))

    async def disconnect(self, close_code):
        # Leave order group
        await self.channel_layer.group_discard(
            self.order_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'location_update' and self.scope["user"].user_type == 'driver':
                await self.handle_location_update(text_data_json.get('data', {}))
            elif message_type == 'status_update':
                await self.handle_status_update(text_data_json.get('data', {}))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))

    async def handle_location_update(self, data):
        """Handle driver location updates"""
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        accuracy = data.get('accuracy', 0)
        speed = data.get('speed')
        heading = data.get('heading')

        if latitude and longitude:
            # Save location to database
            await self.save_driver_location(
                self.scope["user"], latitude, longitude, 
                accuracy, speed, heading
            )

            # Broadcast location update to order group
            await self.channel_layer.group_send(
                self.order_group_name,
                {
                    'type': 'location_update',
                    'data': {
                        'latitude': latitude,
                        'longitude': longitude,
                        'accuracy': accuracy,
                        'speed': speed,
                        'heading': heading,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )

    async def handle_status_update(self, data):
        """Handle order status updates"""
        status = data.get('status')
        message = data.get('message', '')
        
        if status:
            await self.save_order_tracking(
                self.order_id, status, message, self.scope["user"]
            )

            # Broadcast status update
            await self.channel_layer.group_send(
                self.order_group_name,
                {
                    'type': 'status_update',
                    'data': {
                        'status': status,
                        'message': message,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )

    # WebSocket message handlers
    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'data': event['data']
        }))

    async def status_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'data': event['data']
        }))

    async def order_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data']
        }))

    # Database operations
    @database_sync_to_async
    def check_tracking_permission(self, user, order_id):
        try:
            order = Order.objects.get(id=order_id)
            return (user == order.customer or 
                   user == order.vendor.user or 
                   (order.driver and user == order.driver.user) or
                   user.user_type == 'admin')
        except Order.DoesNotExist:
            return False

    @database_sync_to_async
    def get_order_tracking_data(self, order_id):
        try:
            order = Order.objects.select_related('customer', 'vendor', 'driver').get(id=order_id)
            tracking_updates = list(order.tracking_updates.all()[:10])
            
            data = {
                'order_number': order.order_number,
                'status': order.status,
                'customer': order.customer.username,
                'vendor': order.vendor.business_name,
                'driver': order.driver.user.username if order.driver else None,
                'pickup_address': order.pickup_address,
                'delivery_address': order.delivery_address,
                'estimated_delivery_time': order.estimated_delivery_time.isoformat() if order.estimated_delivery_time else None,
                'tracking_updates': [
                    {
                        'status': update.status,
                        'message': update.message,
                        'timestamp': update.timestamp.isoformat(),
                        'latitude': float(update.latitude) if update.latitude else None,
                        'longitude': float(update.longitude) if update.longitude else None,
                    }
                    for update in tracking_updates
                ]
            }
            
            # Add live tracking data if available
            if hasattr(order, 'live_tracking') and order.live_tracking.is_active:
                live_tracking = order.live_tracking
                data['live_tracking'] = {
                    'current_latitude': float(live_tracking.current_latitude) if live_tracking.current_latitude else None,
                    'current_longitude': float(live_tracking.current_longitude) if live_tracking.current_longitude else None,
                    'last_update': live_tracking.last_update.isoformat() if live_tracking.last_update else None,
                    'distance_to_pickup': float(live_tracking.distance_to_pickup) if live_tracking.distance_to_pickup else None,
                    'distance_to_delivery': float(live_tracking.distance_to_delivery) if live_tracking.distance_to_delivery else None,
                }
            
            return data
        except Order.DoesNotExist:
            return None

    @database_sync_to_async
    def save_driver_location(self, user, latitude, longitude, accuracy, speed, heading):
        try:
            driver = user.driver
            location = DriverLocation.objects.create(
                driver=driver,
                latitude=latitude,
                longitude=longitude,
                accuracy=accuracy,
                speed=speed,
                heading=heading
            )
            
            # Update driver's current location
            driver.update_location(latitude, longitude)
            
            # Update live tracking if exists
            live_tracking = LiveTracking.objects.filter(
                driver=driver,
                is_active=True
            ).first()
            
            if live_tracking:
                live_tracking.current_latitude = latitude
                live_tracking.current_longitude = longitude
                live_tracking.last_update = timezone.now()
                live_tracking.save()
            
            return location
        except Exception as e:
            print(f"Error saving driver location: {e}")
            return None

    @database_sync_to_async
    def save_order_tracking(self, order_id, status, message, user):
        try:
            order = Order.objects.get(id=order_id)
            tracking = OrderTracking.objects.create(
                order=order,
                status=status,
                message=message,
                updated_by=user
            )
            return tracking
        except Exception as e:
            print(f"Error saving order tracking: {e}")
            return None

class DriverLocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if isinstance(user, AnonymousUser) or user.user_type != 'driver':
            await self.close()
            return

        self.driver_group_name = f'driver_{user.id}'
        
        # Join driver group
        await self.channel_layer.group_add(
            self.driver_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave driver group
        await self.channel_layer.group_discard(
            self.driver_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'location_update':
                await self.handle_location_update(text_data_json.get('data', {}))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))

    async def handle_location_update(self, data):
        """Handle continuous driver location updates"""
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        accuracy = data.get('accuracy', 0)
        speed = data.get('speed')
        heading = data.get('heading')

        if latitude and longitude:
            await self.save_driver_location(
                self.scope["user"], latitude, longitude, 
                accuracy, speed, heading
            )

    # Assignment notifications
    async def assignment_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'assignment',
            'data': event['data']
        }))

    @database_sync_to_async
    def save_driver_location(self, user, latitude, longitude, accuracy, speed, heading):
        try:
            driver = user.driver
            DriverLocation.objects.create(
                driver=driver,
                latitude=latitude,
                longitude=longitude,
                accuracy=accuracy,
                speed=speed,
                heading=heading
            )
            
            # Update driver's current location
            driver.update_location(latitude, longitude)
            
            return True
        except Exception as e:
            print(f"Error saving driver location: {e}")
            return False
