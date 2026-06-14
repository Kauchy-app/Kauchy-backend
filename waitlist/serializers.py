from rest_framework import serializers
from .models import WaitListModel

class WaitlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaitListModel
        fields = ('email',)