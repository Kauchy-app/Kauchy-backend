from rest_framework import serializers
from .models import Product, ProductReviews


class ProductReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ProductReviews
        fields = ['id', 'user', 'user_name', 'rating', 'review', 'created_at']
        read_only_fields = ['user', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    vendor_username = serializers.CharField(source="vendor_id.username", read_only=True)
    vendor_email = serializers.CharField(source="vendor_id.email", read_only=True)
    vendor_rating = serializers.CharField(source="vendor_id.rating", read_only=True)
    institute = serializers.CharField(source="vendor_id.institute", read_only=True)
    pfp = serializers.URLField(source="vendor_id.profile_url", read_only=True)
    has_liked = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = "__all__"

    def get_has_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.product_likes.filter(user=request.user).exists()
        return False