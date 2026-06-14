from django.shortcuts import render
from httpcore import request
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import CartItem
from .serializers import CartItemSerializer
from Products_app.models import Product
from drf_spectacular.utils import extend_schema,OpenApiParameter,OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework.permissions import IsAuthenticated
from Products_app.serializers import ProductSerializer
from Products_app.models import Product


class CarItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request, pk):
        try:
            product_instance = Product.objects.get(id=pk)
        except Product.DoesNotExist:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        # Prevent the product owner from adding their own product to cart
        if product_instance.vendor_id == request.user:
            return Response({"message": "You cannot add your own product to cart"}, status=status.HTTP_400_BAD_REQUEST)
        try:

            product = CartItem.objects.get(product=pk, user=request.user)
            product.quantity += 1
            product.save()
            return Response({"message":"Product added to cart"},status=status.HTTP_201_CREATED)
        except CartItem.DoesNotExist:
            data = {
                "product":pk
            }





        serializer=CartItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data,status=status.HTTP_201_CREATED)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        try:
            cart_item = CartItem.objects.get(pk=pk, user=request.user)
        except CartItem.DoesNotExist:
            return Response({"message": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get("quantity")
        if quantity is not None:
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    cart_item.delete()
                    return Response({"message": "Item removed from cart"}, status=status.HTTP_200_OK)

                # Check stock
                if cart_item.product.quantity < quantity:
                    return Response({
                        "message": f"Only {cart_item.product.quantity} items available in stock."
                    }, status=status.HTTP_400_BAD_REQUEST)

                cart_item.quantity = quantity
                cart_item.save()
            except ValueError:
                return Response({"message": "Invalid quantity"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def delete(self,request,pk):
        try:
            cart_item=CartItem.objects.get(pk=pk,user=request.user)
            cart_item.delete()
            return Response({"message": "Product deleted successfully"}, status=status.HTTP_200_OK)
        except CartItem.DoesNotExist:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        
        
class GetCartItemView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self,request):
        cart_items=CartItem.objects.filter(user=request.user)
        
        
        serializer=CartItemSerializer(cart_items,many=True)
    

        return Response(serializer.data,status=status.HTTP_200_OK)

