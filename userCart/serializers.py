from rest_framework import serializers
from .models import CartItem
from rest_framework.exceptions import ValidationError

class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.product_name", read_only=True)
    product_image = serializers.JSONField(source="product.image_url", read_only=True)
    product_price = serializers.IntegerField(source="product.price", read_only=True)
    vendor_name = serializers.CharField(source="product.vendor_id.username", read_only=True)
    class Meta:
        model = CartItem
        fields = '__all__'
        extra_kwargs = {
            "user": {"read_only": True}
        }

    def create(self, validated_data, **kwargs):
        # `user` is passed from the view as serializer.save(user=request.user)
        user = kwargs.get('user')
        product = validated_data.get('product')
        if user and product and getattr(product, 'vendor_id', None) == user:
            raise ValidationError("You cannot add your own product to cart")
        return super().create(validated_data)