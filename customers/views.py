from re import U
import cloudinary
import cloudinary.uploader
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from account.models import CustomUserModel
from .models import TopCustomers, TopVendors, VendorProfiles, VendorContents, Follow, ContentLike, ContentReview
from .serializers import TopCustomersSerializer, TopVendorsSerializer, VendorContentSerializer, VendorProfilesSerializer, FollowSerializer, ContentLikeSerializer, ContentReviewSerializer
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from notification.utils import send_notification_to_user
from Products_app.models import Product
from Products_app.serializers import ProductSerializer
from algorithm.utils import personalized_feed
from algorithm.scoring import add_vendor_affinity
from algorithm.models import UserVendorAffinity
import random

class TopCustomersView(APIView):
    @extend_schema(
            summary="Retrieve Top  Customers",
            description="Get a list of top 10 customers based on their total purchases.",
            responses={200: TopCustomersSerializer(many=True)},
    )
    def get(self, request):
        top_customers = TopCustomers.objects.all().order_by('-total_purchases')[:10]
        serializer = TopCustomersSerializer(top_customers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class TopVendorsView(APIView):
    @extend_schema(
            summary="Retrieve Top Vendors",
            description="Get a list of top 10 vendors based on their total sales.",
            responses={200: TopVendorsSerializer(many=True)},
    )
    def get(self, request):
        top_vendors = TopVendors.objects.all().order_by('-total_sales')[:10]
        serializer = TopVendorsSerializer(top_vendors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create Vendor Profile",
        description="Create a vendor profile for the authenticated user.",
        request=VendorProfilesSerializer,
        responses={201: VendorProfilesSerializer},
        examples=[
            OpenApiExample(
                'Create Vendor Profile Example',
                summary='Example of creating a vendor profile',
                description='An example request to create a vendor profile.',
                value={
                    "bio": "Experienced vendor specializing in electronics.",
                    "profile_picture": "http://example.com/images/profile.jpg",
                },
            ),
        ]
    )
    def post(self, request):
        if request.user.role != 'vendor':
            return Response(
                {"error": "Only vendors can create profiles"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            if VendorProfiles.objects.filter(user=request.user).exists():
                return Response(
                    {"error": "Profile already exists. Use edit endpoint to update."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data = request.data.copy()
            data['user'] = request.user.id
            
            serializer = VendorProfilesSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class EditProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Edit Vendor Profile",
        description="Update vendor profile information. Only the profile owner can edit.",
        request=VendorProfilesSerializer,
        responses={200: VendorProfilesSerializer},
        examples=[
            OpenApiExample(
                'Edit Profile Example',
                summary='Example of editing a vendor profile',
                description='An example request to update vendor profile.',
                value={
                    "bio": "Updated bio text",
                    "profile_picture": "http://example.com/images/new_profile.jpg",
                },
            ),
        ]
    )
    def put(self, request, pk):
        if request.user.role != 'vendor':
            return Response(
                {"error": "Only vendors can edit profiles"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            profile = VendorProfiles.objects.get(pk=pk)
            
            if profile.user != request.user:
                return Response(
                    {"error": "You can only edit your own profile"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = VendorProfilesSerializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except VendorProfiles.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeleteProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Delete Vendor Profile",
        description="Permanently delete vendor profile and user account. Only the profile owner can delete.",
        responses={204: None},
    )
    def delete(self, request, pk):
        if request.user.role != 'vendor':
            return Response(
                {"error": "Only vendors can delete profiles"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            profile = VendorProfiles.objects.get(pk=pk)
            
            if profile.user != request.user:
                return Response(
                    {"error": "You can only delete your own profile"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            user = CustomUserModel.objects.get(id=profile.user.id)
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except VendorProfiles.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserDeleteProfile(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Delete User Account",
        description="Permanently delete the current user's account and all associated data.",
        responses={204: None},
    )
    def delete(self, request):
        try:
            user = request.user
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UploadContentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'vendor':
            return Response(
                {"error": "Only vendors can upload content"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Debug logging
            # print(f"FILES received: {list(request.FILES.keys())}")
            # print(f"DATA received: {list(request.data.keys())}")
            
            # Get the uploaded files
            video_file = request.FILES.get('video')
            picture_file = request.FILES.get('pictures')
            
            # Validate that at least one file is provided
            if not video_file and not picture_file:
                return Response(
                    {"error": "You must upload either a video or pictures."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate that only one type is uploaded
            if video_file and picture_file:
                return Response(
                    {"error": "You can only upload either a video or pictures, not both."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Upload to Cloudinary and get the secure URL
            video_url = None
            picture_url = None
            
            try:
                if video_file:
                    print(f"Uploading video: {video_file.name}, size: {video_file.size}")
                    
                    upload_result = cloudinary.uploader.upload(
                        video_file,
                        resource_type="video",
                        folder=f"vendor_content/{request.user.id}",
                        chunk_size=6000000,
                        timeout=600,
                        eager_async=True,
                        invalidate=True
                    )
                    
                    print(f"Cloudinary upload result: {upload_result}")
                    video_url = upload_result['secure_url']
                
                if picture_file:
                    print(f"Uploading picture: {picture_file.name}")
                    
                    upload_result = cloudinary.uploader.upload(
                        picture_file,
                        resource_type="image",
                        folder=f"vendor_content/{request.user.id}"
                    )
                    
                    picture_url = upload_result['secure_url']
                
                content = VendorContents.objects.create(
                    user=request.user,
                    caption=request.data.get('caption', ''),
                    video=video_url,
                    pictures=picture_url
                )
                
                serializer = VendorContentSerializer(content, context={'request': request})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
            except cloudinary.exceptions.Error as e:
                print(f"Cloudinary error: {str(e)}")
                return Response(
                    {"error": f"Failed to upload to Cloudinary: {str(e)}"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Exception as e:
            print(f"General error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GetMyContents(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get Vendor Profile and Contents",
        description="Retrieve vendor profile with paginated content feed.",
        parameters=[
            OpenApiParameter(name='page', location=OpenApiParameter.QUERY, description='Page number', type=OpenApiTypes.INT)
        ],
        responses={200: dict},
    )
    def get(self, request):
        contents = VendorContents.objects.filter(user=request.user)
        serializer = VendorContentSerializer(contents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FollowVendorView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Follow Vendor",
        description="Follow a vendor to see their content in your feed.",
        responses={201: FollowSerializer},
    )
    def post(self, request, vendor_id):
        try:
            vendor = CustomUserModel.objects.get(id=vendor_id, role='vendor')
            
            if request.user == vendor:
                return Response(
                    {"error": "You cannot follow yourself"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if already following
            if Follow.objects.filter(follower=request.user, vendor=vendor).exists():
                return Response(
                    {"error": "You are already following this vendor"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            follow = Follow.objects.create(follower=request.user, vendor=vendor)
            serializer = FollowSerializer(follow)
            
            # Get updated follower count
            vendor_profile = VendorProfiles.objects.get(user=vendor)
            
            return Response({
                **serializer.data,
                "vendor_followers_count": vendor_profile.followers_count,
                "message": "Successfully followed vendor"
            }, status=status.HTTP_201_CREATED)
        
        except CustomUserModel.DoesNotExist:
            return Response({"error": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Unfollow Vendor",
        description="Unfollow a vendor to stop seeing their content in your feed.",
        responses={200: dict},
    )
    def delete(self, request, vendor_id):
        try:
            vendor = CustomUserModel.objects.get(id=vendor_id, role='vendor')
            follow = Follow.objects.get(follower=request.user, vendor=vendor)
            follow.delete()
            
            # Get updated follower count
            vendor_profile = VendorProfiles.objects.get(user=vendor)
            
            return Response({
                "message": "Successfully unfollowed",
                "vendor_followers_count": vendor_profile.followers_count
            }, status=status.HTTP_200_OK)
        
        except CustomUserModel.DoesNotExist:
            return Response({"error": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)
        except Follow.DoesNotExist:
            return Response({"error": "You are not following this vendor"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LikeContentView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Like Content",
        description="Like a piece of vendor content.",
        responses={201: ContentLikeSerializer},
    )
    def post(self, request, content_id):
        try:
            content = VendorContents.objects.get(id=content_id)
            like, created = ContentLike.objects.get_or_create(user=request.user, content=content)
            serializer = ContentLikeSerializer(like)

            if created and request.user != content.user:
                add_vendor_affinity(request.user, content.user)
                send_notification_to_user(
                    user=content.user,
                    title="New Like on Content",
                    message=f"{request.user.username} liked your content '{content.caption or 'Untitled'}'.",
                    notification_type="like",
                    link=f"/vendor-profile?vendorId={content.user.id}"
                )
            
            return Response({
                **serializer.data,
                "message": "Successfully liked content" if created else "Already liked content"
            }, status=status.HTTP_201_CREATED)
        
        except VendorContents.DoesNotExist:
            return Response({"error": "Content not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Unlike Content",
        description="Remove your like from vendor content.",
        responses={200: dict},
    )
    def delete(self, request, content_id):
        try:
            content = VendorContents.objects.get(id=content_id)
            deleted, _ = ContentLike.objects.filter(user=request.user, content=content).delete()
            if deleted:
                add_vendor_affinity(request.user, content.user, delta=-1)
            content.refresh_from_db()
            
            return Response({
                "message": "Successfully unliked",
                "content_likes_count": content.likes_count
            }, status=status.HTTP_200_OK)
        
        except VendorContents.DoesNotExist:
            return Response({"error": "Content not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReviewContentView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create Content Review",
        description="Submit a review for vendor content. Only buyers can review.",
        request=ContentReviewSerializer,
        responses={201: ContentReviewSerializer},
    )
    def post(self, request, content_id):
        if request.user.role != 'buyer':
            return Response(
                {"error": "Only buyers can review content"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            content = VendorContents.objects.get(id=content_id)
            
            
            serializer = ContentReviewSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=request.user, content=content)
                if request.user != content.user:
                    send_notification_to_user(
                        user=content.user,
                        title="New Comment on Content",
                        message=f"{request.user.username} commented on your content '{content.caption or 'Untitled'}'.",
                        notification_type="comment",
                        link=f"/vendor-profile?vendorId={content.user.id}"
                    )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except VendorContents.DoesNotExist:
            return Response({"error": "Content not found"}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Update Content Review",
        description="Edit an existing review for vendor content.",
        request=ContentReviewSerializer,
        responses={200: ContentReviewSerializer},
    )
    def put(self, request, content_id):
        if request.user.role != 'buyer':
            return Response(
                {"error": "Only buyers can review content"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            content = VendorContents.objects.get(id=content_id)
            review = ContentReview.objects.get(user=request.user, content=content)
            
            serializer = ContentReviewSerializer(review, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except VendorContents.DoesNotExist:
            return Response({"error": "Content not found"}, status=status.HTTP_404_NOT_FOUND)
        except ContentReview.DoesNotExist:
            return Response({"error": "Review not found"}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @extend_schema(
        summary="Delete Content Review",
        description="Delete your review from vendor content.",
        responses={204: None},
    )
    def delete(self, request, content_id):
        try:
            content = VendorContents.objects.get(id=content_id)
            review = ContentReview.objects.get(user=request.user, content=content)
            review.delete()
            return Response({"message": "Review deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        
        except VendorContents.DoesNotExist:
            return Response({"error": "Content not found"}, status=status.HTTP_404_NOT_FOUND)
        except ContentReview.DoesNotExist:
            return Response({"error": "Review not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetContentReviewsView(APIView):
    @extend_schema(
        summary="Get Content Reviews",
        description="Retrieve all reviews for specific vendor content with pagination.",
        parameters=[
            OpenApiParameter(name='page', location=OpenApiParameter.QUERY, description='Page number', type=OpenApiTypes.INT)
        ],
        responses={200: dict},
    )
    def get(self, request, content_id):
        try:
            content = VendorContents.objects.get(id=content_id)
            reviews = content.content_reviews.all()
            
            # Configure pagination
            paginator = PageNumberPagination()
            paginator.page_size = 10
            paginated_reviews = paginator.paginate_queryset(reviews, request)
            
            serializer = ContentReviewSerializer(paginated_reviews, many=True)
            
            return Response({
                "reviews": serializer.data,
                "total_reviews": reviews.count(),
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link()
            }, status=status.HTTP_200_OK)
        
        except VendorContents.DoesNotExist:
            return Response({"error": "Content not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetUserProfile(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get Current User Profile",
        description="Retrieve the authenticated user's profile including following count and list.",
        responses={200: dict},
    )
    def get(self, request):
        following_count = Follow.objects.filter(follower=request.user).count()
        following = Follow.objects.filter(follower=request.user).select_related('vendor')
        
        following_data = [{
            'vendor_username': follow.vendor.username,
        } for follow in following]
        
        return Response({
            'following_count': following_count,
            'following': following_data
        }, status=status.HTTP_200_OK)
    

class GetVendorContents(APIView):
    def get(self, request, pk):
        contents = VendorContents.objects.filter(user=pk)
        serializer = VendorContentSerializer(contents, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class IncrementContentView(APIView):
    permission_classes = []

    @extend_schema(
        summary="Increment Content Views",
        description="Increment the view count for a specific piece of vendor content uniquely.",
        responses={200: dict},
    )
    def post(self, request, content_id):
        from django.db.models import F
        from usersearch.models import ContentView
        try:
            content = VendorContents.objects.get(id=content_id)
            auth_user = request.user
            
            incremented = False
            if auth_user.is_authenticated:
                if auth_user != content.user:
                    _, created = ContentView.objects.get_or_create(user=auth_user, content=content)
                    if created:
                        VendorContents.objects.filter(id=content_id).update(views_count=F('views_count') + 1)
                        content.refresh_from_db()
                        incremented = True
            else:
                # For anonymous users, we can increment views
                VendorContents.objects.filter(id=content_id).update(views_count=F('views_count') + 1)
                content.refresh_from_db()
                incremented = True

            return Response(
                {
                    "message": "View count updated successfully" if incremented else "View count already registered",
                    "views": content.views_count
                },
                status=status.HTTP_200_OK
            )
        except VendorContents.DoesNotExist:
            return Response(
                {"error": "Content not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetAllContents(APIView):
    def get(self, request):
        contents = VendorContents.objects.all().order_by('-id')[:100]
        serializer = VendorContentSerializer(contents, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class FeedView(APIView):
    """Unified feed endpoint that returns products and content mixed together."""

    def get(self, request):
        user = request.user

        vendor_id = request.query_params.get('vendor_id')

        # Get products
        if vendor_id:
            products = Product.objects.select_related('vendor_id').filter(vendor_id=vendor_id)
        elif user.is_authenticated:
            products = personalized_feed(user)
        else:
            products = Product.objects.select_related('vendor_id').all()

        # Get contents
        if vendor_id:
            contents = list(VendorContents.objects.select_related('user').filter(user_id=vendor_id).order_by('-uploaded_at')[:100])
        else:
            contents = list(VendorContents.objects.select_related('user').all().order_by('-uploaded_at')[:100])
            if user.is_authenticated:
                # Seen content sinks to the bottom; higher vendor-affinity first,
                # newest first as the tiebreak.
                from usersearch.models import ContentView
                seen_content_ids = set(
                    ContentView.objects.filter(user=user).values_list('content_id', flat=True)
                )
                affinity = {a.vendor_id: a.score for a in UserVendorAffinity.objects.filter(user=user)}
                contents.sort(key=lambda c: (c.id in seen_content_ids, -affinity.get(c.user_id, 0), -c.id))

        # Serialize both
        product_data = ProductSerializer(products, many=True, context={'request': request}).data
        content_data = VendorContentSerializer(contents, many=True, context={'request': request}).data

        # Tag each item with its feed_type
        for p in product_data:
            p['feed_type'] = 'product'
        for c in content_data:
            c['feed_type'] = 'content'

        # Interleave: ~2 products then 1 content, preserving personalized order
        mixed = []
        pi, ci = 0, 0
        while pi < len(product_data) or ci < len(content_data):
            # Add up to 2 products
            for _ in range(2):
                if pi < len(product_data):
                    mixed.append(product_data[pi])
                    pi += 1
            # Add 1 content
            if ci < len(content_data):
                mixed.append(content_data[ci])
                ci += 1

        return Response(mixed, status=status.HTTP_200_OK)
