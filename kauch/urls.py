from django.urls import path
from .views import (
    MyKauchesView,
    CreateKauchView,
    KauchDetailView,
    KauchFollowToggleView,
    FollowingKauchesView,
    KauchFeedView,
    KauchPostsView,
    PostDetailView,
    PostLikeToggleView,
    PostCommentsView,
)

urlpatterns = [
    path('', CreateKauchView.as_view(), name='create-kauch'),
    path('my-kauches/', MyKauchesView.as_view(), name='my-kauches'),
    path('following/', FollowingKauchesView.as_view(), name='kauch-following'),
    path('feed/', KauchFeedView.as_view(), name='kauch-feed'),
    path('posts/<int:post_id>/like/', PostLikeToggleView.as_view(), name='kauch-post-like'),
    path('posts/<int:post_id>/comments/', PostCommentsView.as_view(), name='kauch-post-comments'),
    path('posts/<int:post_id>/', PostDetailView.as_view(), name='kauch-post-detail'),
    path('<int:kauch_id>/', KauchDetailView.as_view(), name='kauch-detail'),
    path('<int:kauch_id>/follow/', KauchFollowToggleView.as_view(), name='kauch-follow'),
    path('<int:kauch_id>/posts/', KauchPostsView.as_view(), name='kauch-posts'),
]
