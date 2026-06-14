from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import DisputeSerializer
from .models import DisputeModel
from rest_framework.permissions import IsAuthenticated, IsAdminUser

# Create your views here.



class CreateDisputeView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user = request.user
        data = request.data

        serializer = DisputeSerializer(data=data)

        if serializer.is_valid():
            serializer.save(user=user)
            return Response({"message":"Dispute sent successfully"}, status=status.HTTP_201_CREATED)
        return Response({"errors":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class GetDisputeView(APIView):
    permission_classes=[IsAdminUser]
    def get(self, request):
        data = DisputeModel.objects.all()

        serializer = DisputeSerializer(data, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)