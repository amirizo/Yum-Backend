from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PaymentMethod, Payment, Refund, PayoutRequest
from orders.models import Order
import re

User = get_user_model()

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'payment_type', 'card_brand', 'card_last4', 
                 'card_exp_month', 'card_exp_year', 'mobile_provider',
                 'mobile_money_number', 'is_default', 'created_at']
        read_only_fields = ['id', 'created_at']

class PaymentIntentCreateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(choices=[
        ('card', 'Credit/Debit Card'),
        ('mobile_money', 'Mobile Money'),
        ('cash', 'Cash on Delivery'),
    ])
    
    # Mobile money fields
    mobile_provider = serializers.ChoiceField(
        choices=[
            ('vodacom', 'Vodacom M-Pesa'),
            ('tigo', 'Tigo Pesa'),
            ('airtel', 'Airtel Money'),
            ('halopesa', 'HaloPesa'),
        ],
        required=False
    )
    phone_number = serializers.CharField(max_length=15, required=False)
    
    # Card fields
    save_payment_method = serializers.BooleanField(default=False)

    def validate_order_id(self, value):
        user = self.context['request'].user
        try:
            order = Order.objects.get(id=value, customer=user, payment_status='pending')
            return value
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found or already paid")
    
    def validate_phone_number(self, value):
        if value:
            # Remove any spaces, dashes, or plus signs
            cleaned_number = re.sub(r'[\s\-\+]', '', value)
            
            # Check if it's a valid Tanzanian mobile number
            if not re.match(r'^(255|0)?[67]\d{8}$', cleaned_number):
                raise serializers.ValidationError(
                    "Please enter a valid Tanzanian mobile number (e.g., 0712345678 or 255712345678)"
                )
            
            # Normalize to international format
            if cleaned_number.startswith('0'):
                cleaned_number = '255' + cleaned_number[1:]
            elif not cleaned_number.startswith('255'):
                cleaned_number = '255' + cleaned_number
                
            return cleaned_number
        return value
    
    def validate(self, data):
        payment_type = data.get('payment_type')
        
        if payment_type == 'mobile_money':
            if not data.get('phone_number'):
                raise serializers.ValidationError({
                    'phone_number': 'Phone number is required for mobile money payments'
                })
            if not data.get('mobile_provider'):
                raise serializers.ValidationError({
                    'mobile_provider': 'Mobile money provider is required'
                })
        
        return data

class PaymentConfirmSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()

class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = ['id', 'order_number', 'amount', 'currency', 'payment_type',
                 'status', 'clickpesa_order_reference', 'clickpesa_payment_reference',
                 'mobile_provider', 'created_at', 'processed_at']
        read_only_fields = ['id', 'created_at', 'processed_at']

class MobileMoneyPaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    mobile_number = serializers.CharField(max_length=15)
    mobile_provider = serializers.ChoiceField(choices=[
        ('vodacom', 'Vodacom M-Pesa'),
        ('tigo', 'Tigo Pesa'),
        ('airtel', 'Airtel Money'),
        ('halopesa', 'Halo Pesa')
    ])

    def validate_mobile_number(self, value):
        # Validate Tanzanian mobile number format
        if not value.startswith('+255'):
            if value.startswith('0'):
                value = '+255' + value[1:]
            elif value.startswith('255'):
                value = '+' + value
            else:
                value = '+255' + value
        
        # Basic validation for Tanzanian numbers
        if len(value) != 13:
            raise serializers.ValidationError("Invalid Tanzanian mobile number format")
        
        return value

class RefundCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ['payment', 'amount', 'reason', 'description']

    def validate_payment(self, value):
        if value.status != 'completed':
            raise serializers.ValidationError("Can only refund completed payments")
        return value

    def validate_amount(self, value):
        payment = self.initial_data.get('payment')
        if payment:
            try:
                payment_obj = Payment.objects.get(id=payment)
                total_refunded = sum(r.amount for r in payment_obj.refunds.filter(status='completed'))
                if value + total_refunded > payment_obj.amount:
                    raise serializers.ValidationError("Refund amount exceeds available balance")
            except Payment.DoesNotExist:
                pass
        return value

class RefundSerializer(serializers.ModelSerializer):
    payment_order_number = serializers.CharField(source='payment.order.order_number', read_only=True)
    
    class Meta:
        model = Refund
        fields = ['id', 'payment_order_number', 'amount', 'currency', 
                 'status', 'reason', 'description', 'created_at', 'processed_at']
        read_only_fields = ['id', 'created_at', 'processed_at']

class PayoutRequestSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.first_name', read_only=True)
    
    class Meta:
        model = PayoutRequest
        fields = ['id', 'vendor_name', 'amount', 'currency', 'status', 
                 'bank_account_last4', 'description', 'created_at', 'processed_at']
        read_only_fields = ['id', 'vendor_name', 'created_at', 'processed_at']

class PayoutRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRequest
        fields = ['amount', 'description']

    def validate_amount(self, value):
        # Minimum payout amount in TZS
        if value < 25000:  # 25,000 TZS minimum
            raise serializers.ValidationError("Minimum payout amount is 25,000 TZS")
        return value
