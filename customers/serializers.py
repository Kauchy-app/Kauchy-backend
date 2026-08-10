from rest_framework import serializers
from .models import TopCustomers, TopVendors, VendorProfiles, Follow

class TopCustomersSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='customer.username', read_only=True)
    institute = serializers.CharField(source='customer.institute', read_only=True)
    pfp = serializers.CharField(source="customer.profile_url", read_only=True)
    class Meta:
        model = TopCustomers
        fields = '__all__'
         

class TopVendorsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="vendor.username", read_only=True)
    institute = serializers.CharField(source="vendor.institute", read_only=True)
    pfp = serializers.CharField(source="vendor.profile_url", read_only=True)
    rating = serializers.CharField(source="vendor.rating", read_only=True)

    class Meta:
        model = TopVendors
        fields = '__all__'


class VendorProfilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProfiles
        fields = '__all__'


class FollowSerializer(serializers.ModelSerializer):
    follower_email = serializers.EmailField(source='follower.email', read_only=True)
    vendor_email = serializers.EmailField(source='vendor.email', read_only=True)
    vendor_followers_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Follow
        fields = ['id', 'follower', 'vendor', 'follower_email', 'vendor_email', 'vendor_followers_count', 'created_at']
        read_only_fields = ['follower', 'created_at']
    
    def get_vendor_followers_count(self, obj):
        try:
            profile = VendorProfiles.objects.get(user=obj.vendor)
            return profile.followers_count
        except VendorProfiles.DoesNotExist:
            return 0
