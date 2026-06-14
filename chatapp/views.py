from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from .models import ConversationModel
from rest_framework.permissions import IsAuthenticated
from .serializers import ConversationSerializer
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

# Create your views here.
class CreateConversationView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self, request, pk):
        user = request.user
        if user.id == pk:
            return Response({"message":"Cannot contact yourself"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            vendor = User.objects.get(id=pk)
        except User.DoesNotExist:
            return Response({"message":"Vendor does not exist"}, status=status.HTTP_404_NOT_FOUND)
        
        if user.id > vendor.id:
            _, created = ConversationModel.objects.get_or_create(buyer=vendor, vendor=user)
        else:
            _, created = ConversationModel.objects.get_or_create(buyer=user, vendor=vendor)

        if created:
            return Response({"message":"Chat created successfully"}, status=status.HTTP_201_CREATED)
        return Response({"message":"Chat already exists"}, status=status.HTTP_200_OK)


class MessageFileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        conversation_id = request.data.get('conversation_id')
        text = request.data.get('text', '')
        file = request.FILES.get('file')

        if not conversation_id:
            return Response({"message": "conversation_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = ConversationModel.objects.get(id=conversation_id)
        except ConversationModel.DoesNotExist:
            return Response({"message": "Conversation does not exist"}, status=status.HTTP_404_NOT_FOUND)

        # Check if user is part of the conversation
        if conversation.vendor != user and conversation.buyer != user:
            return Response({"message": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        # Create message
        from .models import MessageModel
        message = MessageModel.objects.create(
            conversation=conversation,
            sender=user,
            text=text,
            file=file
        )

        file_url = message.file.url if message.file else None

        # Broadcast via Channels
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{conversation_id}",
            {
                'type': "chat_message",
                "conversation_id": conversation_id,
                "message": message.text,
                "file_url": file_url,
                "sender": message.sender.id,
                'timestamp': message.timestamp.isoformat()
            }
        )

        from .serializers import MessageSerializer
        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
