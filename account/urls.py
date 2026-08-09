from django.urls import path
from .views import GetUserProfile, GoogleAuthView, CompleteProfileView, CheckEmailView

urlpatterns = [
    path('user/<int:pk>', GetUserProfile.as_view(), name='getuser'),
    path('google/', GoogleAuthView.as_view(), name='google-auth'),
    path('complete-profile/', CompleteProfileView.as_view(), name='complete-profile'),
    path('check-email/', CheckEmailView.as_view(), name='check-email'),
]