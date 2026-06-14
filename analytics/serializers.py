from rest_framework import serializers
from .models import DailyAnalytics, ProductStockSnapshot, TopSellingProduct

class DailyAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyAnalytics
        fields = ['date', 'total_revenue', 'total_sales_quantity', 'active_products_count', 'total_stock_units']

class ProductStockSnapshotSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    
    class Meta:
        model = ProductStockSnapshot
        fields = ['id', 'product', 'product_name', 'quantity', 'recorded_at']

class TopSellingProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    product_price = serializers.DecimalField(source='product.price', read_only=True, max_digits=10, decimal_places=2)
    image_url = serializers.JSONField(source="product.image_url", read_only=True)
    
    class Meta:
        model = TopSellingProduct
        fields = ['id', 'product', 'product_name', 'product_price', 'units_sold', 'revenue_generated', 'period_start', 'period_end', 'rank', 'image_url']