from rest_framework import serializers
from .models import BuyerWallet, VendorWallet, TopUpMOdel


class BuyerWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model=BuyerWallet
        fields="__all__"

class VendorWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model=VendorWallet
        fields="__all__"

class TopUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopUpMOdel
        fields = ["id", "amount", "status", "transaction_type", "reference"]