from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions, status
from decimal import Decimal
from orders.models import calculate_delivery_fee, calculate_distance

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def test_delivery_calculations(request):
    """Test delivery fee calculations with various scenarios"""
    
    # Test scenarios
    test_cases = [
        {
            "description": "Distance 2.5km (≤3km rate)",
            "vendor_lat": -6.7924,
            "vendor_lng": 39.2083,
            "customer_lat": -6.8104,
            "customer_lng": 39.2083,
            "expected_logic": "2.5km × 2000 TSH/km = 5000 TSH"
        },
        {
            "description": "Distance 5km (≥4km rate)",
            "vendor_lat": -6.7924,
            "vendor_lng": 39.2083,
            "customer_lat": -6.8400,
            "customer_lng": 39.2083,
            "expected_logic": "5km × 700 TSH/km = 3500 TSH"
        },
        {
            "description": "Distance 1km (≤3km rate)",
            "vendor_lat": -6.7924,
            "vendor_lng": 39.2083,
            "customer_lat": -6.8014,
            "customer_lng": 39.2083,
            "expected_logic": "1km × 2000 TSH/km = 2000 TSH"
        },
        {
            "description": "Distance 3km (≤3km rate)",
            "vendor_lat": -6.7924,
            "vendor_lng": 39.2083,
            "customer_lat": -6.8194,
            "customer_lng": 39.2083,
            "expected_logic": "3km × 2000 TSH/km = 6000 TSH"
        },
        {
            "description": "Distance 10km (≥4km rate)",
            "vendor_lat": -6.7924,
            "vendor_lng": 39.2083,
            "customer_lat": -6.8824,
            "customer_lng": 39.2083,
            "expected_logic": "10km × 700 TSH/km = 7000 TSH"
        }
    ]
    
    results = []
    
    for case in test_cases:
        # Calculate actual distance
        distance = calculate_distance(
            case['vendor_lat'], case['vendor_lng'],
            case['customer_lat'], case['customer_lng']
        )
        
        # Calculate delivery fee
        fee = calculate_delivery_fee(
            case['customer_lat'], case['customer_lng'],
            case['vendor_lat'], case['vendor_lng']
        )
        
        # Determine rate used
        if distance <= 3:
            rate = 2000
            rate_description = "≤3km rate"
        else:
            rate = 700
            rate_description = "≥4km rate"
        
        result = {
            "test_case": case['description'],
            "vendor_coordinates": [case['vendor_lat'], case['vendor_lng']],
            "customer_coordinates": [case['customer_lat'], case['customer_lng']],
            "calculated_distance_km": round(distance, 2),
            "rate_used": f"{rate} TSH/km",
            "rate_description": rate_description,
            "calculated_fee": fee,
            "calculation_formula": f"{distance:.2f}km × {rate} TSH/km = {fee} TSH",
            "expected_logic": case['expected_logic']
        }
        
        results.append(result)
    
    return Response({
        "message": "Delivery fee calculation test results",
        "calculation_rules": {
            "rule_1": "Distance ≤ 3km: 2000 TSH per km",
            "rule_2": "Distance ≥ 4km: 700 TSH per km"
        },
        "test_results": results,
        "summary": {
            "total_tests": len(results),
            "note": "All calculations use actual GPS distance between coordinates"
        }
    })

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def custom_delivery_test(request):
    """Test delivery fee with custom coordinates"""
    try:
        vendor_lat = float(request.data.get('vendor_latitude'))
        vendor_lng = float(request.data.get('vendor_longitude'))
        customer_lat = float(request.data.get('customer_latitude'))
        customer_lng = float(request.data.get('customer_longitude'))
        
        # Calculate distance
        distance = calculate_distance(vendor_lat, vendor_lng, customer_lat, customer_lng)
        
        # Calculate delivery fee
        fee = calculate_delivery_fee(customer_lat, customer_lng, vendor_lat, vendor_lng)
        
        # Determine rate
        if distance <= 3:
            rate = 2000
            rate_description = "≤3km rate: 2000 TSH per km"
        else:
            rate = 700
            rate_description = "≥4km rate: 700 TSH per km"
        
        return Response({
            "test_input": {
                "vendor_coordinates": [vendor_lat, vendor_lng],
                "customer_coordinates": [customer_lat, customer_lng]
            },
            "calculation_result": {
                "distance_km": round(distance, 2),
                "rate_applied": rate_description,
                "delivery_fee": fee,
                "currency": "TSH",
                "formula": f"{distance:.2f}km × {rate} TSH/km = {fee} TSH"
            },
            "validation": {
                "status": "success",
                "message": "Delivery fee calculated successfully"
            }
        })
        
    except (ValueError, TypeError) as e:
        return Response({
            "error": "Invalid coordinates provided",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            "error": "Calculation failed",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
