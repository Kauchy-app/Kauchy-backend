import json

from django.db.models import F, Q

import cloudinary
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.openapi import OpenApiTypes

from Products_app.models import Product
from .models import (
    KauchModel,
    PostModel,
    PostLike,
    PostComment,
    KauchFollow,
    Bookmark,
    MAX_KAUCHES_PER_VENDOR,
)
from .serializers import (
    KauchSerializer,
    KauchMiniSerializer,
    PostSerializer,
    CommentSerializer,
)
from .utils import upload_to_cloudinary, detect_media_type

# Create your views here.


def _parse_product_ids(raw):
    """Accept tagged_product_ids as a JSON string, list, or comma-separated string."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        values = raw
    elif isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            values = parsed if isinstance(parsed, list) else [parsed]
        except (ValueError, json.JSONDecodeError):
            values = [part for part in raw.split(',') if part.strip()]
    else:
        values = [raw]

    ids = []
    for value in values:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return ids


class MyKauchesView(APIView):
    """1.1 List the authenticated vendor's Kauches / 1.2 Create a Kauch."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List my Kauches",
        description="Returns the list of Kauches owned by the authenticated vendor.",
        responses={200: KauchSerializer(many=True)},
    )
    def get(self, request):
        kauches = KauchModel.objects.filter(owner=request.user)
        serializer = KauchSerializer(kauches, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateKauchView(APIView):
    """1.2 Create a Kauch (vendor only, max 2)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create a Kauch",
        description="Creates a new Kauch. Fails (400) if the vendor already has 2 Kauches.",
        request=KauchSerializer,
        responses={201: KauchSerializer},
    )
    def post(self, request):
        user = request.user
        if getattr(user, "role", None) != "vendor":
            return Response(
                {"error": "Only vendors can create a Kauch."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if KauchModel.objects.filter(owner=user).count() >= MAX_KAUCHES_PER_VENDOR:
            return Response(
                {"error": f"You can only own up to {MAX_KAUCHES_PER_VENDOR} Kauches."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = (request.data.get("name") or "").strip()
        if not name:
            return Response(
                {"error": "name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        avatar_url = None
        avatar_file = request.FILES.get("avatar")
        if avatar_file:
            try:
                avatar_url = upload_to_cloudinary(avatar_file, f"kauch/avatars/{user.id}", resource_type="image")
            except cloudinary.exceptions.Error as e:
                return Response(
                    {"error": "Failed to upload avatar.", "details": str(e)},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        kauch = KauchModel.objects.create(
            owner=user,
            name=name,
            description=request.data.get("description", "") or "",
            avatar_url=avatar_url,
        )
        return Response(KauchSerializer(kauch).data, status=status.HTTP_201_CREATED)


class KauchDetailView(APIView):
    """1.3 Get details of a specific Kauch."""

    @extend_schema(
        summary="Get Kauch details",
        responses={200: KauchSerializer},
    )
    def get(self, request, kauch_id):
        kauch = get_object_or_404(KauchModel, pk=kauch_id)
        serializer = KauchSerializer(kauch, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class FollowingKauchesView(APIView):
    """List the Kauches the authenticated user follows (for the sidebar)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Kauches I follow",
        responses={200: KauchMiniSerializer(many=True)},
    )
    def get(self, request):
        kauches = KauchModel.objects.filter(followers__user=request.user).distinct()
        return Response(KauchMiniSerializer(kauches, many=True).data, status=status.HTTP_200_OK)


class KauchFollowToggleView(APIView):
    """Follow / unfollow a Kauch."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Toggle follow on a Kauch",
        responses={200: dict},
    )
    def post(self, request, kauch_id):
        kauch = get_object_or_404(KauchModel, pk=kauch_id)
        follow, created = KauchFollow.objects.get_or_create(kauch=kauch, user=request.user)

        if not created:
            follow.delete()
            kauch.refresh_from_db()
            return Response(
                {"is_following": False, "followers_count": kauch.followers_count},
                status=status.HTTP_200_OK,
            )

        kauch.refresh_from_db()
        return Response(
            {"is_following": True, "followers_count": kauch.followers_count},
            status=status.HTTP_200_OK,
        )


class KauchFeedView(APIView):
    """2.1 Get the homepage feed (chronological)."""

    @extend_schema(
        summary="Kauch feed",
        description="Returns a chronological feed of Kauch posts.",
        responses={200: PostSerializer(many=True)},
    )
    def get(self, request):
        posts = (
            PostModel.objects.select_related('kauch')
            .prefetch_related('tagged_products')
            .all()
        )
        serializer = PostSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class KauchPostsView(APIView):
    """2.2 List posts for a Kauch / 2.3 Create a post (owner only)."""

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return []

    @extend_schema(
        summary="List posts for a Kauch",
        responses={200: PostSerializer(many=True)},
    )
    def get(self, request, kauch_id):
        kauch = get_object_or_404(KauchModel, pk=kauch_id)
        posts = (
            kauch.posts.select_related('kauch')
            .prefetch_related('tagged_products')
            .all()
        )
        serializer = PostSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create a Kauch post",
        description="Create a post in a Kauch. Only the Kauch owner may post.",
        responses={201: PostSerializer},
    )
    def post(self, request, kauch_id):
        kauch = get_object_or_404(KauchModel, pk=kauch_id)
        if kauch.owner != request.user:
            return Response(
                {"error": "Only the owner of this Kauch can post."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Accept multiple files under the "media" key. A post is either ONE video,
        # ONE voice note, or MANY images — never a mix.
        media_files = request.FILES.getlist("media")
        media_urls = []
        media_type = PostModel.IMAGE

        if media_files:
            types = {detect_media_type(f) for f in media_files}
            if ("video" in types or "audio" in types) and len(media_files) > 1:
                return Response(
                    {"error": "A post can contain either one video, one voice note, or multiple images."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if "video" in types:
                media_type = PostModel.VIDEO
            elif "audio" in types:
                media_type = PostModel.AUDIO
            else:
                media_type = PostModel.IMAGE

            # Cloudinary stores audio under the "video" resource type.
            upload_resource = "video" if media_type in (PostModel.VIDEO, PostModel.AUDIO) else "image"
            try:
                for f in media_files:
                    url = upload_to_cloudinary(
                        f, f"kauch/posts/{kauch.id}", resource_type=upload_resource
                    )
                    media_urls.append(url)
            except cloudinary.exceptions.Error as e:
                return Response(
                    {"error": "Failed to upload media.", "details": str(e)},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        post = PostModel.objects.create(
            kauch=kauch,
            description=request.data.get("description", "") or "",
            media_type=media_type,
            # Keep the legacy single field pointing at the first item.
            media_url=media_urls[0] if media_urls else None,
            media_urls=media_urls,
        )

        product_ids = _parse_product_ids(request.data.get("tagged_product_ids"))
        if product_ids:
            products = Product.objects.filter(id__in=product_ids)
            post.tagged_products.set(products)

        serializer = PostSerializer(post, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PostDetailView(APIView):
    """Get a single post by id (used for shareable post pages / link previews)."""

    @extend_schema(
        summary="Get a single post",
        responses={200: PostSerializer},
    )
    def get(self, request, post_id):
        post = get_object_or_404(
            PostModel.objects.select_related('kauch').prefetch_related('tagged_products'),
            pk=post_id,
        )
        serializer = PostSerializer(post, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PostLikeToggleView(APIView):
    """3.1 Like / unlike a post."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Toggle like on a post",
        responses={200: dict},
    )
    def post(self, request, post_id):
        post = get_object_or_404(PostModel, pk=post_id)
        like, created = PostLike.objects.get_or_create(post=post, user=request.user)

        if not created:
            like.delete()
            post.refresh_from_db()
            return Response(
                {"liked": False, "likes_count": post.likes_count},
                status=status.HTTP_200_OK,
            )

        post.refresh_from_db()
        return Response(
            {"liked": True, "likes_count": post.likes_count},
            status=status.HTTP_200_OK,
        )



class PostShareView(APIView):
    """Record a share event on a post — atomically increments shares_count."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Share a post",
        description="Increments the post's share counter by 1 and returns the updated count.",
        responses={200: dict},
    )
    def post(self, request, post_id):
        post = get_object_or_404(PostModel, pk=post_id)
        PostModel.objects.filter(pk=post.pk).update(shares_count=F('shares_count') + 1)
        post.refresh_from_db(fields=['shares_count'])
        return Response({"shares_count": post.shares_count}, status=status.HTTP_200_OK)


class PostBookmarkToggleView(APIView):
    """Toggle a bookmark (save) on a post."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Toggle bookmark on a post",
        responses={200: dict},
    )
    def post(self, request, post_id):
        post = get_object_or_404(PostModel, pk=post_id)
        bookmark, created = Bookmark.objects.get_or_create(post=post, user=request.user)

        if not created:
            bookmark.delete()
            return Response({"bookmarked": False}, status=status.HTTP_200_OK)

        return Response({"bookmarked": True}, status=status.HTTP_200_OK)


class BookmarksListView(APIView):
    """List the authenticated user's bookmarked posts."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List my bookmarked posts",
        responses={200: PostSerializer(many=True)},
    )
    def get(self, request):
        posts = (
            PostModel.objects.filter(bookmarks__user=request.user)
            .select_related('kauch')
            .prefetch_related('tagged_products')
            .order_by('-bookmarks__created_at')
        )
        serializer = PostSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PostCommentsView(APIView):
    """3.2 Comment on a post / 3.3 List comments."""

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return []

    @extend_schema(
        summary="List comments for a post",
        responses={200: CommentSerializer(many=True)},
    )
    def get(self, request, post_id):
        post = get_object_or_404(PostModel, pk=post_id)
        comments = post.comments.select_related('user').all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create a comment on a post",
        request=CommentSerializer,
        responses={201: CommentSerializer},
    )
    def post(self, request, post_id):
        post = get_object_or_404(PostModel, pk=post_id)
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response(
                {"error": "text is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent = None
        parent_id = request.data.get("parent")
        if parent_id:
            # Reply must target a comment on this same post; ignore otherwise.
            parent = PostComment.objects.filter(pk=parent_id, post=post).first()

        comment = PostComment.objects.create(post=post, user=request.user, text=text, parent=parent)
        serializer = CommentSerializer(comment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class KauchSearchView(APIView):
    @extend_schema(
        summary="Search Kauches",
        description=(
            "Filter Kauches whose name or description contains the query string. "
            "Returns up to 20 results ordered by follower count (most popular first). "
            "An empty or missing `q` returns an empty list."
        ),
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search term (matched against name and description)',
                required=False,
            )
        ],
        responses={200: KauchSerializer(many=True)},
    )
    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        if not q:
            return Response([], status=status.HTTP_200_OK)

        kauches = (
            KauchModel.objects
            .filter(Q(name__icontains=q) | Q(description__icontains=q))
            .order_by('-followers_count')[:20]
        )
        serializer = KauchSerializer(kauches, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
