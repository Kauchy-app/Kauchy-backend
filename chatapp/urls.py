from django.urls import path
from .views import CreateConversationView, MessageFileUploadView

urlpatterns = [
    path('create/<int:pk>', CreateConversationView.as_view(), name="Create conversations"),
    path('upload/', MessageFileUploadView.as_view(), name='chat-upload'),
]