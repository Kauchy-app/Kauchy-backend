from rest_framework import serializers
from .models import DisputeModel


class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeModel
        fields = '__all__'
        read_only_fields = ['user']