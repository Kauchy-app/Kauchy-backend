from django.urls import path
from .views import TopCustomersView, TopVendorsView, UpdateProfileView, EditProfileView, DeleteProfileView, UserDeleteProfile, FollowVendorView, GetUserProfile


urlpatterns = [
    path('top-customers/', TopCustomersView.as_view(), name='top-customers'),
    path('top-vendors/', TopVendorsView.as_view(), name='top-vendors'),
    path('profile/update/', UpdateProfileView.as_view(), name='update-profile'),
    path('profile/edit/<int:pk>/', EditProfileView.as_view(), name='edit-profile'),
    path('profile/delete/<int:pk>/', DeleteProfileView.as_view(), name='delete-profile'),
    path('user/delete/', UserDeleteProfile.as_view(), name='user-delete-profile'),
    path('vendor/<int:vendor_id>/follow/', FollowVendorView.as_view(), name='follow-vendor'),
    path('profile/user/', GetUserProfile.as_view(), name='get-user-profile'),
]