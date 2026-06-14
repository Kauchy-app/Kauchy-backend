from django.urls import path
from .views import GetMyContents, TopCustomersView, TopVendorsView, UpdateProfileView, EditProfileView, DeleteProfileView, UploadContentView, UserDeleteProfile, ReviewContentView, LikeContentView, FollowVendorView, GetContentReviewsView, GetUserProfile, GetVendorContents, IncrementContentView, GetAllContents, FeedView


urlpatterns = [
    path('top-customers/', TopCustomersView.as_view(), name='top-customers'),
    path('top-vendors/', TopVendorsView.as_view(), name='top-vendors'),
    path('profile/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('profile/edit/<int:pk>/', EditProfileView.as_view(), name='edit-profile'),
    path('profile/delete/<int:pk>/', DeleteProfileView.as_view(), name='delete-profile'),
    path('user/delete/', UserDeleteProfile.as_view(), name='user-delete-profile'),
    path('mycontents/', GetMyContents.as_view(), name='get-profile'),
    path('content/upload/', UploadContentView.as_view(), name='upload-content'),
    path('content/<int:content_id>/reviews/', GetContentReviewsView.as_view(), name='get-content-reviews'),
    path('content/<int:content_id>/review/', ReviewContentView.as_view(), name='review-content'),
    path('content/<int:content_id>/like/', LikeContentView.as_view(), name='like-content'),
    path('content/<int:content_id>/view/', IncrementContentView.as_view(), name='view-content'),
    path('vendor/<int:vendor_id>/follow/', FollowVendorView.as_view(), name='follow-vendor'),
    path('profile/user/', GetUserProfile.as_view(), name='get-user-profile'),
    path('vendorcontents/<int:pk>', GetVendorContents.as_view(), name="vendor_contents"),
    path('allcontents/', GetAllContents.as_view(), name='all-contents'),
    path('feed/', FeedView.as_view(), name='unified-feed'),
]