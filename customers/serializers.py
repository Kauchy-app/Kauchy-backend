from rest_framework import serializers
from .models import TopCustomers, TopVendors, VendorContents, VendorProfiles, Follow, ContentLike, ContentReview

class TopCustomersSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='customer.username', read_only=True)
    institute = serializers.CharField(source='customer.institute', read_only=True)
    pfp = serializers.CharField(source="customer.profile_url", read_only=True)
    class Meta:
        model = TopCustomers
        fields = '__all__'
         

class TopVendorsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="vendor.username", read_only=True)
    institute = serializers.CharField(source="vendor.institute", read_only=True)
    pfp = serializers.CharField(source="vendor.profile_url", read_only=True)
    rating = serializers.CharField(source="vendor.rating", read_only=True)

    class Meta:
        model = TopVendors
        fields = '__all__'


class VendorProfilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProfiles
        fields = '__all__'


class VendorContentSerializer(serializers.ModelSerializer):
    content_type = serializers.SerializerMethodField()
    is_liked_by_user = serializers.SerializerMethodField()
    views = serializers.IntegerField(source='views_count', read_only=True)
    vendor_username = serializers.CharField(source='user.username', read_only=True)
    vendor_id = serializers.IntegerField(source='user.id', read_only=True)
    pfp = serializers.URLField(source='user.profile_url', read_only=True)
    
    class Meta:
        model = VendorContents
        fields = ['id', 'user', 'video', 'pictures', 'caption', 'uploaded_at', 'content_type', 'likes_count', 'reviews_count', 'is_liked_by_user', 'views', 'vendor_username', 'vendor_id', 'pfp']
        
    def get_content_type(self, obj):
        if obj.video:
            return 'video'
        elif obj.pictures:
            return 'picture'
        return None
    
    def get_is_liked_by_user(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ContentLike.objects.filter(user=request.user, content=obj).exists()
        return False
    
    def validate(self, data):
        video = data.get('video')
        pictures = data.get('pictures')
        
        if video and pictures:
            raise serializers.ValidationError("You can only upload either a video or pictures, not both.")
        
        if not video and not pictures:
            raise serializers.ValidationError("You must upload either a video or pictures.")
        
        return data


class FollowSerializer(serializers.ModelSerializer):
    follower_email = serializers.EmailField(source='follower.email', read_only=True)
    vendor_email = serializers.EmailField(source='vendor.email', read_only=True)
    vendor_followers_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Follow
        fields = ['id', 'follower', 'vendor', 'follower_email', 'vendor_email', 'vendor_followers_count', 'created_at']
        read_only_fields = ['follower', 'created_at']
    
    def get_vendor_followers_count(self, obj):
        try:
            profile = VendorProfiles.objects.get(user=obj.vendor)
            return profile.followers_count
        except VendorProfiles.DoesNotExist:
            return 0


class ContentLikeSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    content_likes_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContentLike
        fields = ['id', 'user', 'content', 'user_email', 'content_likes_count', 'created_at']
        read_only_fields = ['user', 'created_at']
    
    def get_content_likes_count(self, obj):
        return obj.content.likes_count


class ContentReviewSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = ContentReview
        fields = ['id', 'user', 'content','comment', 'user_email', 'created_at', 'updated_at']
        read_only_fields = ['user', 'created_at', 'updated_at', 'content']
    
    def validate_comment(self, value):
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Comment must be at least 3 characters long")
        return value