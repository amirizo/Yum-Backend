from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import DeliveryAddress
from .serializers import DeliveryAddressSerializer
from decimal import Decimal
import googlemaps
from django.conf import settings

User = get_user_model()

class SavedDeliveryAddressListView(generics.ListCreateAPIView):
    """List and create saved delivery addresses for authenticated users"""
    serializer_class = DeliveryAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DeliveryAddress.objects.filter(user=self.request.user).order_by('-is_default', '-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class SavedDeliveryAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a saved delivery address"""
    serializer_class = DeliveryAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DeliveryAddress.objects.filter(user=self.request.user)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def validate_delivery_address(request):
    """Validate delivery address and return geocoded information"""
    try:
        address_text = request.data.get('address')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not address_text and (not latitude or not longitude):
            return Response({
                'error': 'Either address text or coordinates are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # If coordinates provided, validate and reverse geocode
        if latitude and longitude:
            try:
                lat_decimal = Decimal(str(latitude))
                lng_decimal = Decimal(str(longitude))
                
                # Validate coordinate ranges
                if not (-90 <= lat_decimal <= 90):
                    return Response({
                        'error': 'Invalid latitude. Must be between -90 and 90'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if not (-180 <= lng_decimal <= 180):
                    return Response({
                        'error': 'Invalid longitude. Must be between -180 and 180'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Reverse geocode to get address
                if hasattr(settings, 'GOOGLE_MAPS_API_KEY') and settings.GOOGLE_MAPS_API_KEY:
                    gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
                    reverse_result = gmaps.reverse_geocode((float(latitude), float(longitude)))
                    
                    if reverse_result:
                        formatted_address = reverse_result[0]['formatted_address']
                    else:
                        formatted_address = address_text or f"Location at {latitude}, {longitude}"
                else:
                    formatted_address = address_text or f"Location at {latitude}, {longitude}"
                
                return Response({
                    'valid': True,
                    'address': formatted_address,
                    'latitude': float(latitude),
                    'longitude': float(longitude),
                    'message': 'Address validated successfully'
                })
                
            except (ValueError, TypeError):
                return Response({
                    'error': 'Invalid coordinate format'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # If only address text provided, geocode it
        if address_text and (hasattr(settings, 'GOOGLE_MAPS_API_KEY') and settings.GOOGLE_MAPS_API_KEY):
            gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
            geocode_result = gmaps.geocode(address_text, region='TZ')
            
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                return Response({
                    'valid': True,
                    'address': geocode_result[0]['formatted_address'],
                    'latitude': location['lat'],
                    'longitude': location['lng'],
                    'place_id': geocode_result[0].get('place_id'),
                    'message': 'Address geocoded successfully'
                })
            else:
                return Response({
                    'error': 'Address could not be geocoded. Please provide coordinates.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'error': 'Unable to validate address. Please provide both address and coordinates.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'error': f'Address validation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def calculate_delivery_preview(request):
    """Calculate delivery fee preview for given addresses"""
    try:
        vendor_id = request.data.get('vendor_id')
        customer_latitude = request.data.get('customer_latitude')
        customer_longitude = request.data.get('customer_longitude')
        
        if not all([vendor_id, customer_latitude, customer_longitude]):
            return Response({
                'error': 'vendor_id, customer_latitude, and customer_longitude are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get vendor
        from authentication.models import Vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id, status='active')
        except Vendor.DoesNotExist:
            return Response({
                'error': 'Vendor not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get vendor location
        vendor_location = vendor.primary_location
        if not vendor_location:
            return Response({
                'error': 'Vendor location not available'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate delivery fee
        from .models import calculate_delivery_fee, calculate_distance
        
        delivery_fee = calculate_delivery_fee(
            float(customer_latitude),
            float(customer_longitude),
            float(vendor_location.latitude),
            float(vendor_location.longitude)
        )
        
        distance_km = calculate_distance(
            float(customer_latitude),
            float(customer_longitude),
            float(vendor_location.latitude),
            float(vendor_location.longitude)
        )
        
        # Calculate estimated delivery time
        base_prep_time = vendor.average_preparation_time
        travel_time = int(distance_km * 3)  # 3 minutes per km
        estimated_time = base_prep_time + travel_time
        
        return Response({
            'vendor_name': vendor.business_name,
            'vendor_address': vendor_location.address,
            'distance_km': round(distance_km, 2),
            'delivery_fee': delivery_fee,
            'currency': 'TSH',
            'estimated_delivery_time': estimated_time,
            'calculation_method': '≤3km: 2000 TSH/km, ≥4km: 700 TSH/km',
            'message': f'Delivery fee calculated for {distance_km:.2f}km distance'
        })
        
    except Exception as e:
        return Response({
            'error': f'Delivery calculation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
