from rest_framework import serializers
from .models import ProductView, ContentView, SearchQuery
from Products_app.serializers import ProductSerializer
from customers.serializers import VendorContentSerializer


class ProductViewSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = ProductView
        fields = ['id', 'user', 'product', 'product_details', 'viewed_at', 'view_duration']
        read_only_fields = ['user', 'viewed_at']


class ContentViewSerializer(serializers.ModelSerializer):
    content_details = VendorContentSerializer(source='content', read_only=True)
    
    class Meta:
        model = ContentView
        fields = ['id', 'user', 'content', 'content_details', 'viewed_at', 'view_duration']
        read_only_fields = ['user', 'viewed_at']


class SearchQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchQuery
        fields = ['id', 'user', 'query', 'searched_at']
        read_only_fields = ['user', 'searched_at']