from rest_framework import serializers
from decimal import Decimal
from .models import Cart, Product, calculate_delivery_fee
from authentication.models import Vendor

class DeliveryAddressCheckoutSerializer(serializers.Serializer):
    """Delivery address serializer for checkout"""
    address = serializers.CharField(max_length=500)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8)
    city = serializers.CharField(max_length=100, required=False)
    state = serializers.CharField(max_length=100, required=False)
    
    landmark = serializers.CharField(max_length=200, required=False)
    delivery_instructions = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_latitude(self, value):
        if not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value
    
    def validate_longitude(self, value):
        if not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value

class PaymentMethodCheckoutSerializer(serializers.Serializer):
    """Payment method serializer for checkout"""
    PAYMENT_TYPES = [
        ('mobile_money', 'Mobile Money'),
        ('card', 'Credit/Debit Card'),
        ('cash', 'Cash on Delivery')
    ]
    
    MOBILE_PROVIDERS = [
        ('mix_by_yas', 'All Networks (Mix by YAS)'),
        ('vodacom', 'Vodacom M-Pesa'),
        ('airtel', 'Airtel Money'),
        ('tigo', 'Tigo Pesa'),
        ('halopesa', 'Halo Pesa')
    ]
    
    payment_type = serializers.ChoiceField(choices=PAYMENT_TYPES)
    phone_number = serializers.CharField(max_length=15, required=False)
    provider = serializers.ChoiceField(choices=MOBILE_PROVIDERS, required=False, default='mix_by_yas')
    save_payment_method = serializers.BooleanField(default=False, required=False)
    
    def validate(self, data):
        if data['payment_type'] == 'mobile_money':
            if not data.get('phone_number'):
                raise serializers.ValidationError("Phone number is required for mobile money payments")
            
            # Validate Tanzanian phone number format
            phone = data['phone_number'].strip()
            if not phone.startswith(('+255', '255', '0')):
                raise serializers.ValidationError("Please provide a valid Tanzanian phone number")
        
        return data

class SavedAddressSerializer(serializers.Serializer):
    """For selecting saved delivery addresses"""
    address_id = serializers.IntegerField()
    use_saved_address = serializers.BooleanField(default=True)

class CheckoutValidationSerializer(serializers.Serializer):
    """Complete checkout validation serializer"""
    vendor_id = serializers.IntegerField()
    delivery_address = DeliveryAddressCheckoutSerializer(required=False)
    saved_address = SavedAddressSerializer(required=False)
    payment_method = PaymentMethodCheckoutSerializer()
    special_instructions = serializers.CharField(max_length=500, required=False, allow_blank=True)
    save_address = serializers.BooleanField(default=False, required=False)
    address_label = serializers.CharField(max_length=50, required=False)
    
    def validate_vendor_id(self, value):
        try:
            vendor = Vendor.objects.get(id=value, status='active')
            return value
        except Vendor.DoesNotExist:
            raise serializers.ValidationError("Vendor not found or inactive")
    
    def validate(self, data):
        request = self.context['request']
        vendor_id = data['vendor_id']
        
        # Validate delivery address
        if data.get('saved_address'):
            # Using saved address
            if not request.user.is_authenticated:
                raise serializers.ValidationError("Must be logged in to use saved addresses")
            
            address_id = data['saved_address']['address_id']
            try:
                from .models import DeliveryAddress
                address = DeliveryAddress.objects.get(id=address_id, user=request.user)
                # Set the delivery address data from saved address
                data['delivery_address'] = {
                    'address': f"{address.street_address}, {address.city}",
                    'latitude': address.latitude,
                    'longitude': address.longitude,
                    'city': address.city,
                    'state': address.state,
                }
            except DeliveryAddress.DoesNotExist:
                raise serializers.ValidationError("Saved address not found")
        
        elif not data.get('delivery_address'):
            raise serializers.ValidationError("Either delivery_address or saved_address is required")
        
        # Get vendor
        vendor = Vendor.objects.get(id=vendor_id)
        
        # Validate vendor has location
        if not vendor.primary_location:
            raise serializers.ValidationError("Vendor location not available for delivery calculation")
        
        # Validate cart exists and is not empty
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user, vendor_id=vendor_id).first()
            if not cart or not cart.items.exists():
                raise serializers.ValidationError("Cart is empty for this vendor")
        else:
            # For anonymous users, check session cart
            session_cart = request.session.get('cart', [])
            if not session_cart:
                raise serializers.ValidationError("Cart is empty")
            
            # Check if session cart has items from this vendor
            vendor_items = [item for item in session_cart 
                          if Product.objects.filter(id=item['product_id'], vendor_id=vendor_id).exists()]
            if not vendor_items:
                raise serializers.ValidationError("Cart has no items from this vendor")
        
        # Validate payment method is supported by vendor
        payment_type = data['payment_method']['payment_type']
        if payment_type == 'mobile_money' and not vendor.accepts_mobile_money:
            raise serializers.ValidationError("Vendor does not accept mobile money payments")
        elif payment_type == 'card' and not vendor.accepts_card:
            raise serializers.ValidationError("Vendor does not accept card payments")
        elif payment_type == 'cash' and not vendor.accepts_cash:
            raise serializers.ValidationError("Vendor does not accept cash payments")
        
        return data

class OrderCalculationSerializer(serializers.Serializer):
    """Serializer for order calculation response"""
    vendor_name = serializers.CharField()
    vendor_id = serializers.IntegerField()
    vendor_address = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    distance_km = serializers.DecimalField(max_digits=8, decimal_places=2)
    estimated_delivery_time = serializers.IntegerField()  # in minutes
    items_count = serializers.IntegerField()
    currency = serializers.CharField(default='TSH')
    delivery_calculation = serializers.CharField()
    payment_methods_accepted = serializers.ListField()
    
class CartItemCheckoutSerializer(serializers.Serializer):
    """Cart item for checkout display"""
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    special_instructions = serializers.CharField(required=False)
