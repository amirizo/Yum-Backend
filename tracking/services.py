import math
from django.utils import timezone
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import (
    DriverLocation, OrderTracking, LiveTracking, 
    TrackingEvent, Geofence, NotificationQueue
)
from orders.models import Order
from authentication.models import Driver

class TrackingService:
    def __init__(self):
        self.channel_layer = get_channel_layer()

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c

    def start_live_tracking(self, order):
        """Start live tracking session for an order"""
        if not order.driver:
            return None

        live_tracking, created = LiveTracking.objects.get_or_create(
            order=order,
            defaults={
                'driver': order.driver,
                'is_active': True
            }
        )

        if not created and not live_tracking.is_active:
            live_tracking.is_active = True
            live_tracking.started_at = timezone.now()
            live_tracking.save()

        return live_tracking

    def end_live_tracking(self, order):
        """End live tracking session for an order"""
        try:
            live_tracking = LiveTracking.objects.get(order=order, is_active=True)
            live_tracking.end_session()
            return True
        except LiveTracking.DoesNotExist:
            return False

    def update_driver_location(self, driver, latitude, longitude, accuracy=0, speed=None, heading=None):
        """Update driver location and handle tracking logic"""
        # Save location
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

        # Update active live tracking sessions
        active_trackings = LiveTracking.objects.filter(
            driver=driver,
            is_active=True
        )

        for live_tracking in active_trackings:
            self.update_live_tracking(live_tracking, latitude, longitude)
            self.check_geofences(live_tracking, latitude, longitude)
            self.broadcast_location_update(live_tracking, location)

        return location

    def update_live_tracking(self, live_tracking, latitude, longitude):
        """Update live tracking with new location data"""
        live_tracking.current_latitude = latitude
        live_tracking.current_longitude = longitude
        live_tracking.last_update = timezone.now()

        # Calculate distances
        order = live_tracking.order
        
        # Distance to pickup (if not picked up yet)
        if order.status in ['assigned', 'ready']:
            live_tracking.distance_to_pickup = self.calculate_distance(
                latitude, longitude,
                float(order.pickup_latitude), float(order.pickup_longitude)
            )

        # Distance to delivery (if picked up)
        if order.status in ['picked_up', 'in_transit']:
            live_tracking.distance_to_delivery = self.calculate_distance(
                latitude, longitude,
                float(order.delivery_latitude), float(order.delivery_longitude)
            )

        live_tracking.save()

    def check_geofences(self, live_tracking, latitude, longitude):
        """Check if driver entered/exited any geofences"""
        order = live_tracking.order
        
        # Check pickup geofence
        pickup_distance = self.calculate_distance(
            latitude, longitude,
            float(order.pickup_latitude), float(order.pickup_longitude)
        )
        
        # If within 100 meters of pickup and status is assigned
        if pickup_distance <= 0.1 and order.status == 'assigned':
            self.create_tracking_event(
                live_tracking, 'geofence_enter',
                'Driver arrived at pickup location',
                latitude, longitude
            )
            self.update_order_status(order, 'driver_arrived_pickup')

        # Check delivery geofence
        delivery_distance = self.calculate_distance(
            latitude, longitude,
            float(order.delivery_latitude), float(order.delivery_longitude)
        )
        
        # If within 100 meters of delivery and status is in_transit
        if delivery_distance <= 0.1 and order.status == 'in_transit':
            self.create_tracking_event(
                live_tracking, 'geofence_enter',
                'Driver arrived at delivery location',
                latitude, longitude
            )
            self.update_order_status(order, 'driver_arrived_delivery')

    def create_tracking_event(self, live_tracking, event_type, description, latitude=None, longitude=None, metadata=None):
        """Create a tracking event"""
        event = TrackingEvent.objects.create(
            live_tracking=live_tracking,
            event_type=event_type,
            description=description,
            latitude=latitude,
            longitude=longitude,
            metadata=metadata or {}
        )
        return event

    def update_order_status(self, order, new_status):
        """Update order status and create tracking record"""
        old_status = order.status
        order.status = new_status
        order.save()

        # Create order tracking record
        OrderTracking.objects.create(
            order=order,
            status=new_status,
            message=f'Status updated from {old_status} to {new_status}'
        )

        # Broadcast status update
        self.broadcast_status_update(order, new_status)

        # Create notifications
        self.create_status_notifications(order, new_status)

    def broadcast_location_update(self, live_tracking, location):
        """Broadcast location update via WebSocket"""
        if not self.channel_layer:
            return

        order_group_name = f'order_{live_tracking.order.id}'
        
        async_to_sync(self.channel_layer.group_send)(
            order_group_name,
            {
                'type': 'location_update',
                'data': {
                    'latitude': float(location.latitude),
                    'longitude': float(location.longitude),
                    'accuracy': location.accuracy,
                    'speed': location.speed,
                    'heading': location.heading,
                    'timestamp': location.timestamp.isoformat(),
                    'distance_to_pickup': float(live_tracking.distance_to_pickup) if live_tracking.distance_to_pickup else None,
                    'distance_to_delivery': float(live_tracking.distance_to_delivery) if live_tracking.distance_to_delivery else None,
                }
            }
        )

    def broadcast_status_update(self, order, status):
        """Broadcast status update via WebSocket"""
        if not self.channel_layer:
            return

        order_group_name = f'order_{order.id}'
        
        async_to_sync(self.channel_layer.group_send)(
            order_group_name,
            {
                'type': 'status_update',
                'data': {
                    'status': status,
                    'message': f'Order status updated to {status}',
                    'timestamp': timezone.now().isoformat()
                }
            }
        )

    def create_status_notifications(self, order, status):
        """Create notifications for status updates"""
        notifications = []
        
        # Customer notification
        if status in ['driver_assigned', 'picked_up', 'delivered']:
            message = self.get_status_message(status, 'customer')
            notifications.append(NotificationQueue(
                recipient=order.customer,
                recipient_type='customer',
                notification_type='order_update',
                title=f'Order {order.order_number} Update',
                message=message,
                order=order
            ))

        # Vendor notification
        if status in ['picked_up', 'delivered']:
            message = self.get_status_message(status, 'vendor')
            notifications.append(NotificationQueue(
                recipient=order.vendor.user,
                recipient_type='vendor',
                notification_type='order_update',
                title=f'Order {order.order_number} Update',
                message=message,
                order=order
            ))

        NotificationQueue.objects.bulk_create(notifications)

    def get_status_message(self, status, recipient_type):
        """Get appropriate message for status and recipient"""
        messages = {
            'driver_assigned': {
                'customer': 'A driver has been assigned to your order and is on the way to pick it up.',
                'vendor': 'A driver has been assigned to pick up the order.'
            },
            'picked_up': {
                'customer': 'Your order has been picked up and is on the way to you.',
                'vendor': 'Your order has been picked up by the driver.'
            },
            'delivered': {
                'customer': 'Your order has been delivered successfully.',
                'vendor': 'Your order has been delivered to the customer.'
            }
        }
        return messages.get(status, {}).get(recipient_type, f'Order status updated to {status}')

    def get_driver_route_optimization(self, driver, orders):
        """Simple route optimization for multiple orders"""
        if not orders:
            return []

        # For now, simple distance-based sorting
        # In production, you'd use a proper routing API
        current_lat = float(driver.current_latitude) if driver.current_latitude else 0
        current_lon = float(driver.current_longitude) if driver.current_longitude else 0

        order_distances = []
        for order in orders:
            distance = self.calculate_distance(
                current_lat, current_lon,
                float(order.pickup_latitude), float(order.pickup_longitude)
            )
            order_distances.append((order, distance))

        # Sort by distance
        order_distances.sort(key=lambda x: x[1])
        return [order for order, distance in order_distances]

    def cleanup_old_locations(self, days=7):
        """Clean up old location data"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        deleted_count = DriverLocation.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()[0]
        return deleted_count
