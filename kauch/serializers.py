from rest_framework import serializers
from .models import KauchModel, PostModel, PostComment
from .utils import cloudinary_video_delivery


class KauchSerializer(serializers.ModelSerializer):
    """Serializes a Kauch as defined in the API contract (section 1)."""
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = KauchModel
        fields = [
            'id', 'name', 'description', 'avatar_url',
            'followers_count', 'created_at', 'owner_username', 'is_following',
        ]
        read_only_fields = ['id', 'avatar_url', 'followers_count', 'created_at']

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.followers.filter(user=request.user).exists()
        return False


class KauchMiniSerializer(serializers.ModelSerializer):
    """Lightweight Kauch info nested inside a post (API contract 2.1)."""

    class Meta:
        model = KauchModel
        fields = ['id', 'name', 'avatar_url']


class TaggedProductSerializer(serializers.Serializer):
    """Minimal product shape for products tagged in a post (API contract 2.1)."""
    id = serializers.IntegerField()
    product_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    image_url = serializers.JSONField()


class PostSerializer(serializers.ModelSerializer):
    kauch = KauchMiniSerializer(read_only=True)
    tagged_products = TaggedProductSerializer(many=True, read_only=True)
    is_liked_by_user = serializers.SerializerMethodField()
    is_bookmarked_by_user = serializers.SerializerMethodField()
    media_url = serializers.SerializerMethodField()
    media_urls = serializers.SerializerMethodField()

    class Meta:
        model = PostModel
        fields = [
            'id', 'kauch', 'description', 'media_type', 'media_url', 'media_urls',
            'tagged_products', 'likes_count', 'comments_count', 'shares_count',
            'bookmarks_count', 'is_liked_by_user', 'is_bookmarked_by_user', 'created_at',
        ]

    def get_media_url(self, obj):
        # Force a desktop-decodable codec for videos (HEVC iPhone uploads
        # otherwise render blank on desktop Chrome/Firefox).
        if obj.media_type == 'video':
            return cloudinary_video_delivery(obj.media_url)
        return obj.media_url

    def get_media_urls(self, obj):
        # Always return a list. Older posts created before multi-media have an
        # empty media_urls list, so fall back to the single media_url.
        urls = obj.media_urls or ([obj.media_url] if obj.media_url else [])
        if obj.media_type == 'video':
            return [cloudinary_video_delivery(u) for u in urls]
        return urls

    def get_is_liked_by_user(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_is_bookmarked_by_user(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmarks.filter(user=request.user).exists()
        return False


class CommentUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    avatar_url = serializers.URLField(source='profile_url')


class CommentSerializer(serializers.ModelSerializer):
    user = CommentUserSerializer(read_only=True)

    class Meta:
        model = PostComment
        fields = ['id', 'user', 'text', 'parent', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
