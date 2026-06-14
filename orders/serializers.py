from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price']

class OrderSerializer(serializers.ModelSerializer):
    buyer_username = serializers.CharField(source='buyer.username', read_only=True)
    vendor_username = serializers.CharField(source='vendor.username', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'buyer', 'buyer_username', 'vendor_username', 'vendor', 'amount', 'status', 'qr_code', 'created_at', 'completed_at', 'items')
        read_only_fields = ('qr_code', 'created_at', 'id')