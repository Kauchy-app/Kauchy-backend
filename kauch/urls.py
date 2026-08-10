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
    PostShareView,
    PostCommentsView,
    PostBookmarkToggleView,
    BookmarksListView,
    KauchSearchView,
)

urlpatterns = [
    path('', CreateKauchView.as_view(), name='create-kauch'),
    path('my-kauches/', MyKauchesView.as_view(), name='my-kauches'),
    path('following/', FollowingKauchesView.as_view(), name='kauch-following'),
    path('feed/', KauchFeedView.as_view(), name='kauch-feed'),
    path('bookmarks/', BookmarksListView.as_view(), name='kauch-bookmarks'),
    path('posts/<str:post_id>/like/', PostLikeToggleView.as_view(), name='kauch-post-like'),
    path('posts/<str:post_id>/share/', PostShareView.as_view(), name='kauch-post-share'),
    path('posts/<str:post_id>/bookmark/', PostBookmarkToggleView.as_view(), name='kauch-post-bookmark'),
    path('posts/<str:post_id>/comments/', PostCommentsView.as_view(), name='kauch-post-comments'),
    path('posts/<str:post_id>/', PostDetailView.as_view(), name='kauch-post-detail'),
    path('search/', KauchSearchView.as_view(), name='kauch-search'),
    path('<str:kauch_id>/', KauchDetailView.as_view(), name='kauch-detail'),
    path('<str:kauch_id>/follow/', KauchFollowToggleView.as_view(), name='kauch-follow'),
    path('<str:kauch_id>/posts/', KauchPostsView.as_view(), name='kauch-posts'),
]
