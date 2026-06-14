from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import WaitlistSerializer
from .utils import send_waitlist_welcome_email

# Create your views here.

class WaitlistViews(APIView):
    def post(self, request):
        data = request.data
        serializer = WaitlistSerializer(data=data)

        if serializer.is_valid():
            waitlist_entry = serializer.save()
            send_waitlist_welcome_email(waitlist_entry.email)
            return Response({"message":"Waitlist Joined Successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
