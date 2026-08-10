from django.urls import path
from .views import GetUserProfile, GoogleAuthView, CompleteProfileView, CheckEmailView, SendOTPView, VerifyOTPView

urlpatterns = [
    path('user/<int:pk>', GetUserProfile.as_view(), name='getuser'),
    path('google/', GoogleAuthView.as_view(), name='google-auth'),
    path('complete-profile/', CompleteProfileView.as_view(), name='complete-profile'),
    path('check-email/', CheckEmailView.as_view(), name='check-email'),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
]