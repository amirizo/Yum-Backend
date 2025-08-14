from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PaymentMethod, Payment, Refund, PayoutRequest
from orders.models import Order

User = get_user_model()

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'payment_type', 'card_brand', 'card_last4', 
                 'card_exp_month', 'card_exp_year', 'mobile_provider', 
                 'mobile_number', 'is_default', 'created_at']
        read_only_fields = ['id', 'created_at']

class PaymentCreateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(choices=[
        ('card', 'Credit/Debit Card'),
        ('mobile_money', 'Mobile Money'),
        ('cash', 'Cash on Delivery')
    ])
    payment_method_id = serializers.CharField(required=False)
    save_payment_method = serializers.BooleanField(default=False)
    
    # Mobile money specific fields
    mobile_provider = serializers.ChoiceField(
        choices=[
            ('vodacom', 'Vodacom M-Pesa'),
            ('tigo', 'Tigo Pesa'),
            ('airtel', 'Airtel Money'),
            ('halopesa', 'Halo Pesa')
        ],
        required=False
    )
    mobile_number = serializers.CharField(max_length=15, required=False)
    
    # Card specific fields
    card_number = serializers.CharField(max_length=19, required=False)
    card_exp_month = serializers.IntegerField(min_value=1, max_value=12, required=False)
    card_exp_year = serializers.IntegerField(min_value=2024, required=False)
    card_cvv = serializers.CharField(max_length=4, required=False)

    def validate_order_id(self, value):
        user = self.context['request'].user
        try:
            order = Order.objects.get(id=value, customer=user, payment_status='pending')
            return value
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found or already paid")

    def validate(self, data):
        payment_type = data.get('payment_type')
        
        if payment_type == 'mobile_money':
            if not data.get('mobile_provider') or not data.get('mobile_number'):
                raise serializers.ValidationError(
                    "Mobile provider and number are required for mobile money payments"
                )
        elif payment_type == 'card':
            if not data.get('payment_method_id'):
                # New card payment
                required_fields = ['card_number', 'card_exp_month', 'card_exp_year', 'card_cvv']
                for field in required_fields:
                    if not data.get(field):
                        raise serializers.ValidationError(f"{field} is required for card payments")
        
        return data

class PaymentConfirmSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    confirmation_code = serializers.CharField(required=False)  # For mobile money confirmations

class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = ['id', 'order_number', 'amount', 'currency', 'payment_type',
                 'status', 'clickpesa_status', 'clickpesa_transaction_id', 
                 'mobile_provider', 'mobile_number', 'receipt_url', 
                 'created_at', 'processed_at']
        read_only_fields = ['id', 'created_at', 'processed_at']

class MobileMoneyPaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    mobile_provider = serializers.ChoiceField(choices=[
        ('vodacom', 'Vodacom M-Pesa'),
        ('tigo', 'Tigo Pesa'),
        ('airtel', 'Airtel Money'),
        ('halopesa', 'Halo Pesa')
    ])
    mobile_number = serializers.CharField(max_length=15)
    save_payment_method = serializers.BooleanField(default=False)

    def validate_order_id(self, value):
        user = self.context['request'].user
        try:
            order = Order.objects.get(id=value, customer=user, payment_status='pending')
            return value
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found or already paid")

    def validate_mobile_number(self, value):
        # Basic Tanzanian mobile number validation
        import re
        if not re.match(r'^(\+255|0)[67]\d{8}$', value):
            raise serializers.ValidationError("Invalid Tanzanian mobile number format")
        return value

class RefundCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ['payment', 'amount', 'reason', 'description']

    def validate_payment(self, value):
        if value.status != 'succeeded':
            raise serializers.ValidationError("Can only refund successful payments")
        return value

    def validate_amount(self, value):
        payment = self.initial_data.get('payment')
        if payment:
            try:
                payment_obj = Payment.objects.get(id=payment)
                total_refunded = sum(r.amount for r in payment_obj.refunds.filter(status='succeeded'))
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
                 'status', 'clickpesa_status', 'reason', 'description', 
                 'created_at', 'processed_at']
        read_only_fields = ['id', 'created_at', 'processed_at']

class PayoutRequestSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.username', read_only=True)
    
    class Meta:
        model = PayoutRequest
        fields = ['id', 'vendor_name', 'amount', 'currency', 'status', 
                 'bank_account_last4', 'mobile_provider', 'mobile_number',
                 'description', 'created_at', 'processed_at']
        read_only_fields = ['id', 'vendor_name', 'created_at', 'processed_at']

class PayoutRequestCreateSerializer(serializers.ModelSerializer):
    payout_method = serializers.ChoiceField(choices=[
        ('bank', 'Bank Account'),
        ('mobile_money', 'Mobile Money')
    ])
    
    class Meta:
        model = PayoutRequest
        fields = ['amount', 'payout_method', 'description']

    def validate_amount(self, value):
        if value < 10000:  # Minimum payout amount in TZS (approximately $4)
            raise serializers.ValidationError("Minimum payout amount is 10,000 TZS")
        return value
