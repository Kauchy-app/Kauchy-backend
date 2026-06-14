from rest_framework import serializers
from .models import *

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'


class BuyerWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuyerWallet
        fields = '__all__'

class VendorWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorWallet
        fields = '__all__'