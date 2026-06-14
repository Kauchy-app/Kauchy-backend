from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Product, ProductReviews, ProductView, ProductLike
from .serializers import ProductSerializer, ProductReviewSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from .supabase_config import supabase
from notification.utils import send_notification_to_user
import os
import time
import uuid
import json
from decimal import Decimal
from storage3.exceptions import StorageApiError
import httpx
from drf_spectacular.utils import extend_schema,OpenApiParameter,OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.db.models import F
from algorithm.utils import personalized_feed
from algorithm.scoring import add_category_interest, add_vendor_affinity
# Create your views here.

class ProductListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    
    @extend_schema(
        summary="List Products",
        description="Retrieve a list of products. Vendors see only their products; buyers see all products.",
        responses={200: ProductSerializer(many=True)},
    )
    def get(self, request):
        auth_user = request.user
        if auth_user.role != "vendor":
            return Response(status=404)
        products = Product.objects.filter(vendor_id=auth_user)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data, status=200)
        


class CreateProductView(APIView):   

    @extend_schema(
        summary="create product",
        description="add product to your product inventory",
        request=ProductSerializer,
        responses={200:dict},
        examples=[
            OpenApiExample(
                "creating product",
                summary="Example of creating of product",
                description="Creating of product",
                value={
                    "product_name":"Bags",
                    "description":"My bags are very cheap and affordable",
                    "price":2000,
                    "quantity":20,
                    "category":"Accessories",
                    "image_url":"img_2312393493/3u4",
                    "rating":4,
                    "view_count":20
                }
            )
            

        ]

    )  
    def post(self, request):
        user = request.user
        # print("User is:", user.id)
        data = request.data
        # print(data)

        # collect uploaded files (if any)
        images = request.FILES.getlist('image_url') if hasattr(request.FILES, 'getlist') else []
        images_urls = []

        # If frontend provided image URLs in JSON body, prefer them unless files exist
        if not images and isinstance(data.get('image_url', None), (list, tuple)):
            images_urls = list(data.get('image_url', []))

        # upload files to supabase storage (ensure unique keys to avoid 409)
        for image in images:
            # read file bytes once
            file_bytes = image.read()
            base, ext = os.path.splitext(image.name or "file")
            unique_name = f"{base}_{uuid.uuid4().hex}{ext}"
            key = f"products/{user.id}/{unique_name}"
            try:
                supabase.storage.from_('marketplace').upload(
                    key,
                    file_bytes,
                    {"content-type": image.content_type}
                )
            except StorageApiError as e:
                # handle duplicate key by retrying with a more unique name
                status_code = getattr(e, "statusCode", None)
                msg = str(e)
                if status_code == 409 or "Duplicate" in msg:
                    unique_name = f"{base}_{int(time.time())}_{uuid.uuid4().hex}{ext}"
                    key = f"products/{user.id}/{unique_name}"
                    supabase.storage.from_('marketplace').upload(
                        key,
                        file_bytes,
                        {"content-type": image.content_type}
                    )
                else:
                    raise
            except httpx.ConnectError as e:
                # Network/DNS issue when contacting Supabase storage
                err_msg = (
                    "Unable to connect to Supabase storage service."
                    " Please check SUPABASE_URL, network/DNS, and that the service is reachable."
                )
                # Log detail to console (server logs)
                print("Supabase connection error:", str(e))
                return Response({"error": err_msg, "details": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
            # get public url and append (normalize dict/str responses)
            url = supabase.storage.from_('marketplace').get_public_url(key)
            # normalize possible response shapes
            if isinstance(url, dict):
                possible = url.get('publicURL') or url.get('public_url') or url.get('publicUrl') or url.get('url')
                if possible:
                    images_urls.append(possible)
                else:
                    # fallback to stringify
                    images_urls.append(str(url))
            else:
                images_urls.append(str(url))

        # Build a clean_data dict that works for both QueryDict (form) and JSON (dict)
        clean_data = {}
        if hasattr(data, "lists"):
            iterator = data.lists()
        else:
            iterator = ((k, v if isinstance(v, list) else [v]) for k, v in data.items())

        for key, value in iterator:
            if len(value) == 1:
                clean_data[key] = value[0]
            else:
                clean_data[key] = value

        # ensure vendor and images are set explicitly
        clean_data['vendor_id'] = user.id
        clean_data['image_url'] = images_urls

        # specs arrives as a JSON string from multipart forms; parse to a dict.
        if 'specs' in clean_data and isinstance(clean_data['specs'], str):
            try:
                parsed = json.loads(clean_data['specs'])
                clean_data['specs'] = parsed if isinstance(parsed, dict) else {}
            except Exception:
                clean_data['specs'] = {}

        # convert numeric types to expected types
        if 'price' in clean_data:
            try:
                clean_data['price'] = Decimal(str(clean_data['price']))
            except Exception:
                pass

        if 'quantity' in clean_data:
            try:
                clean_data['quantity'] = int(clean_data['quantity'])
            except Exception:
                pass

        if 'rating' in clean_data:
            try:
                clean_data['rating'] = int(clean_data['rating'])
            except Exception:
                clean_data['rating'] = 0

        # print("Clean data is:", clean_data)

        serializer = ProductSerializer(data=clean_data)
        if serializer.is_valid():
            product = serializer.save()
            resp = ProductSerializer(product).data
            resp['vendor_username'] = user.username
            return Response(resp, status=201)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        

class ProductDetailView(APIView):
    # permission_classes = [IsAuthenticated]

    @extend_schema(
            summary="Product Detail",
            description="Retrieve, update, or delete a product by its ID.",
            request=ProductSerializer,
            responses={200: ProductSerializer},
    )

    def get(self,request,pk):
        auth_user = request.user
        try:
            # allow any authenticated user to view product details
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductSerializer(product)
        data = serializer.data
        if auth_user.is_authenticated:
            if auth_user != product.vendor_id:
                _, created = ProductView.objects.get_or_create(product=product, user=auth_user)
                if created:
                    Product.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
                # NOTE: a feed view is NOT a preference signal — in a scrolling
                # feed the user doesn't choose what appears. Category/vendor
                # interest is only raised when the user actively likes (see
                # ProductLikeToggleView). We still record ProductView above so
                # seen products can be pushed to the bottom of the feed.
        return Response(data)

    
    def put(self,request,pk):   
        auth_user = request.user
        data = request.data
        data["vendor_id"] = auth_user.id
        # print(request)
        try:
            products = Product.objects.get(pk=pk, vendor_id=auth_user)
        except Product.DoesNotExist:
            return Response({"message":"Product not found"})
        serializer = ProductSerializer(products, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message":"Updated sucessfully"}, status=200)
        return Response({"errors":serializer.errors}, status=400)
    
    def delete(self,request,pk):
        auth_user=request.user
        try:
            product= Product.objects.get(pk=pk,vendor_id=request.user)
        except Product.DoesNotExist:
            return Response({"message":"Product not found"})
        product.delete()
        return Response({"message":"Deleted successfully"})



class AllProductsView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self,request):
        user = request.user
        # print(user)
        if user.is_authenticated:
            # print("hi")
            products = personalized_feed(user)
        else:
            products= Product.objects.all()
        serializer= ProductSerializer(products,many=True, context={'request': request})
        return Response(serializer.data)



class GetVendorProducts(APIView):
    def get(self, request, pk):
        data = Product.objects.filter(vendor_id=pk).select_related('vendor_id')
        serializer = ProductSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductLikeToggleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Toggle Product Like",
        description="Like or unlike a product",
        responses={200: dict},
    )
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        like, created = ProductLike.objects.get_or_create(product=product, user=request.user)

        if not created:
            # Already liked, so unlike it — roll back the preference signal.
            like.delete()
            add_category_interest(request.user, product.category, delta=-1)
            add_vendor_affinity(request.user, product.vendor_id, delta=-1)
            return Response({"message": "Product unliked", "likes_count": product.likes_count, "has_liked": False}, status=status.HTTP_200_OK)

        # A like is an intentional preference signal — raise category & vendor interest.
        add_category_interest(request.user, product.category)
        add_vendor_affinity(request.user, product.vendor_id)

        # Since it was created, save takes care of incrementing the product.likes_count
        product.refresh_from_db()
        if request.user != product.vendor_id:
            send_notification_to_user(
                user=product.vendor_id,
                title="New Like on Product",
                message=f"{request.user.username} liked your product '{product.product_name}'.",
                notification_type="like",
                link=f"/vendor-profile?vendorId={product.vendor_id.id}&itemId={product.id}"
            )
        return Response({"message": "Product liked", "likes_count": product.likes_count, "has_liked": True}, status=status.HTTP_200_OK)


class ProductReviewListCreateView(APIView):
    """List and create reviews for a product."""

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return []

    @extend_schema(
        summary="List Product Reviews",
        description="Retrieve all reviews for a product with pagination.",
        parameters=[
            OpenApiParameter(name='page', location=OpenApiParameter.QUERY, description='Page number', type=OpenApiTypes.INT)
        ],
        responses={200: dict},
    )
    def get(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        reviews = ProductReviews.objects.filter(product=product).order_by('-created_at')

        paginator = PageNumberPagination()
        paginator.page_size = 10
        paginated_reviews = paginator.paginate_queryset(reviews, request)

        serializer = ProductReviewSerializer(paginated_reviews, many=True)

        user_has_purchased = False
        if request.user and request.user.is_authenticated:
            from orders.models import OrderItem
            user_has_purchased = OrderItem.objects.filter(
                product=product,
                order__buyer=request.user,
                order__status='completed'
            ).exists()

        return Response({
            "reviews": serializer.data,
            "total_reviews": reviews.count(),
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "user_has_purchased": user_has_purchased
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create Product Review",
        description="Submit a review for a product. Requires authentication.",
        request=ProductReviewSerializer,
        responses={201: ProductReviewSerializer},
    )
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        # Cannot review your own product
        if request.user == product.vendor_id:
            return Response({"error": "You cannot review your own product"}, status=status.HTTP_403_FORBIDDEN)

        # Check if the user has purchased the product
        from orders.models import OrderItem
        has_purchased = OrderItem.objects.filter(
            product=product,
            order__buyer=request.user,
            order__status='completed'
        ).exists()

        if not has_purchased:
            return Response({"error": "You can only review products you have purchased and completed delivery for."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProductReviewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user, product=product)

            # Update the product's average rating
            all_reviews = ProductReviews.objects.filter(product=product)
            avg_rating = sum(r.rating for r in all_reviews) / all_reviews.count()
            product.rating = round(avg_rating)
            product.save(update_fields=['rating'])

            if request.user != product.vendor_id:
                send_notification_to_user(
                    user=product.vendor_id,
                    title="New Review on Product",
                    message=f"{request.user.username} left a review on '{product.product_name}'.",
                    notification_type="review",
                    link=f"/vendor-profile?vendorId={product.vendor_id.id}&itemId={product.id}"
                )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

