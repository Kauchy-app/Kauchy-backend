from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Count, Q, Avg
from datetime import timedelta
from django.utils import timezone
from .models import ProductView, ContentView, SearchQuery
from .serializers import ProductViewSerializer, ContentViewSerializer, SearchQuerySerializer
from Products_app.models import Product
from customers.models import VendorContents, VendorProfiles
from Products_app.serializers import ProductSerializer


class TrackProductView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        product_id = request.data.get('product_id')
        view_duration = request.data.get('view_duration', 0)
        
        try:
            product = Product.objects.get(id=product_id)
            product_view, created = ProductView.objects.get_or_create(
                user=request.user,
                product=product,
                defaults={'view_duration': view_duration}
            )
            if not created:
                # Update view duration if already exists
                product_view.view_duration = view_duration
                product_view.save()
            
            serializer = ProductViewSerializer(product_view)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)


class TrackContentView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        content_id = request.data.get('content_id')
        view_duration = request.data.get('view_duration', 0)
        
        try:
            content = VendorContents.objects.get(id=content_id)
            content_view, created = ContentView.objects.get_or_create(
                user=request.user,
                content=content,
                defaults={'view_duration': view_duration}
            )
            if not created:
                content_view.view_duration = view_duration
                content_view.save()
            
            serializer = ContentViewSerializer(content_view)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except VendorContents.DoesNotExist:
            return Response({"error": "Content not found"}, status=status.HTTP_404_NOT_FOUND)


class RecentVideosWatchedView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get recent video content views
        recent_videos = ContentView.objects.filter(
            user=request.user,
            content__video__isnull=False
        ).select_related('content', 'content__user')[:20]
        
        serializer = ContentViewSerializer(recent_videos, many=True, context={'request': request})
        return Response({
            'recent_videos': serializer.data,
            'count': recent_videos.count()
        }, status=status.HTTP_200_OK)


class SearchSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        query = request.query_params.get('q', '').strip()
        
        # Get vendors from products the user has viewed
        viewed_product_vendors = ProductView.objects.filter(
            user=user
        ).values_list('product__vendor_name', flat=True).distinct()
        
        # Get vendors from contents the user has viewed
        viewed_content_vendors = ContentView.objects.filter(
            user=user
        ).values_list('content__user', flat=True).distinct()
        
        # Combine and get unique vendor IDs
        vendor_ids = set(list(viewed_product_vendors) + list(viewed_content_vendors))
        
        # Base query for vendors
        vendor_query = VendorProfiles.objects.filter(
            user__role='vendor'
        ).select_related('user')
        
        # If there's a search query, filter vendors by products matching the query
        if query:
            # Find vendors who have products matching the search query
            matching_vendors = Product.objects.filter(
                Q(product_name__icontains=query) | 
                Q(description__icontains=query) |
                Q(category__icontains=query)
            ).values_list('vendor_name', flat=True).distinct()
            
            vendor_query = vendor_query.filter(user__id__in=matching_vendors)
        else:
            # If no query, show vendors based on user's view history
            if vendor_ids:
                vendor_query = vendor_query.filter(user__id__in=vendor_ids)
        
        suggested_vendors = vendor_query[:10]
        
        vendor_data = [{
            'id': profile.user.id,
            'username': profile.user.username,
            'email': profile.user.email,
            'bio': profile.bio,
            'followers_count': profile.followers_count,
            'profile_picture': profile.profile_picture.url if profile.profile_picture else None,
            'total_products': Product.objects.filter(vendor_name=profile.user).count()
        } for profile in suggested_vendors]
        
        # Get suggested products
        if query:
            # Search products by query
            suggested_products = Product.objects.filter(
                Q(product_name__icontains=query) | 
                Q(description__icontains=query) |
                Q(category__icontains=query)
            ).select_related('vendor_name')[:15]
        else:
            # Show products from vendors user has interacted with
            suggested_products = Product.objects.filter(
                vendor_name__id__in=vendor_ids
            ).select_related('vendor_name')[:15]
        
        product_serializer = ProductSerializer(suggested_products, many=True)
        
        # Add vendor username to each product
        products_data = product_serializer.data
        for prod, item in zip(suggested_products, products_data):
            username = prod.vendor_name.username if prod.vendor_name else None
            item['vendor_name'] = username
            item['vendor_username'] = username
        
        # Get recent search queries
        recent_searches = SearchQuery.objects.filter(user=user)[:10]
        search_serializer = SearchQuerySerializer(recent_searches, many=True)
        
        return Response({
            'query': query,
            'suggested_vendors': vendor_data,
            'suggested_products': products_data,
            'recent_searches': search_serializer.data,
            'total_vendors': len(vendor_data),
            'total_products': len(products_data)
        }, status=status.HTTP_200_OK)


class SaveSearchQueryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        query = request.data.get('query', '').strip()
        
        if not query:
            return Response({"error": "Query cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if query already exists for this user recently (within last hour)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        existing_query = SearchQuery.objects.filter(
            user=request.user,
            query__iexact=query,
            searched_at__gte=one_hour_ago
        ).first()
        
        if existing_query:
            # Update timestamp
            existing_query.searched_at = timezone.now()
            existing_query.save()
            serializer = SearchQuerySerializer(existing_query)
        else:
            # Create new search query
            search_query = SearchQuery.objects.create(user=request.user, query=query)
            serializer = SearchQuerySerializer(search_query)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserViewHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get recent product views
        product_views = ProductView.objects.filter(
            user=request.user
        ).select_related('product', 'product__vendor_name')[:20]
        
        # Get recent content views
        content_views = ContentView.objects.filter(
            user=request.user
        ).select_related('content', 'content__user')[:20]
        
        product_serializer = ProductViewSerializer(product_views, many=True)
        content_serializer = ContentViewSerializer(content_views, many=True, context={'request': request})
        
        return Response({
            'product_views': product_serializer.data,
            'content_views': content_serializer.data,
            'total_product_views': product_views.count(),
            'total_content_views': content_views.count()
        }, status=status.HTTP_200_OK)
