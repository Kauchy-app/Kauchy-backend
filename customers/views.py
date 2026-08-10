from re import U
import cloudinary
import cloudinary.uploader
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from account.models import CustomUserModel
from .models import TopCustomers, TopVendors, VendorProfiles, Follow
from .serializers import TopCustomersSerializer, TopVendorsSerializer, VendorProfilesSerializer, FollowSerializer
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
        top_customers = TopCustomers.objects.select_related('customer').all().order_by('-total_purchases')[:10]
        serializer = TopCustomersSerializer(top_customers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class TopVendorsView(APIView):
    @extend_schema(
            summary="Retrieve Top Vendors",
            description="Get a list of top 10 vendors based on their total sales.",
            responses={200: TopVendorsSerializer(many=True)},
    )
    def get(self, request):
        top_vendors = TopVendors.objects.select_related('vendor').all().order_by('-total_sales')[:10]
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
    




class FeedView(APIView):
    """Unified feed endpoint that returns products."""

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

        # Serialize
        product_data = ProductSerializer(products, many=True, context={'request': request}).data

        # Tag each item with its feed_type
        for p in product_data:
            p['feed_type'] = 'product'

        return Response(product_data, status=status.HTTP_200_OK)
