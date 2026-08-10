from rest_framework import serializers
from .models import ProductView, SearchQuery
from Products_app.serializers import ProductSerializer


class ProductViewSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    
    class Meta:
        model = ProductView
        fields = ['id', 'user', 'product', 'product_details', 'viewed_at', 'view_duration']
        read_only_fields = ['user', 'viewed_at']



class SearchQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchQuery
        fields = ['id', 'user', 'query', 'searched_at']
        read_only_fields = ['user', 'searched_at']