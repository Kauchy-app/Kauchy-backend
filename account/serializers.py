from rest_framework import serializers
# from .models import UserProfile
from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from customers.models import VendorProfiles
from .models import CustomUserModel
from paymentapp.models import VendorWallet, BuyerWallet
import requests
from Products_app.supabase_config import supabase
import uuid
import os


User = get_user_model()

class UserCreateSerializer(UserCreateSerializer):
    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ("id","email","username", "password","role","institute", "phone")

    def create(self, validate_data):
        email = validate_data.get('email')
        role = validate_data.get('role')
        username = validate_data.get('username')
        phone = validate_data.get("phone")
        institute = validate_data.get('institute')

        email = email.strip() if email else None


        if not email or not role or not username:
            raise serializers.ValidationError("You must provide email,username and role.")


        
        user = CustomUserModel(
            email=email,
            role=role,
            username=username,
            phone=phone,
            institute=institute,
            profile_completed=True,
        )
        user.set_password(validate_data['password'])
        user.save()
        if role == 'vendor':
            VendorWallet.objects.create(vendor=user, balance=0)
            VendorProfiles.objects.create(user=user)
        elif role == 'buyer':
            BuyerWallet.objects.create(user=user, balance=0)
        return user


    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    


class UserSerializer(UserSerializer):
    profile_picture = serializers.ImageField(
        write_only=True,
        required=False
    )

    # Stored Supabase URL (GET responses)
    profile_url = serializers.URLField(read_only=True)
    class Meta(UserSerializer.Meta):
        model = User
        fields = ("id", "username", "role", "email", "phone", "institute", "rating", "profile_picture", "profile_url", "bio", "profile_completed")
        read_only_fields = ("id", "username", "role", "email", "phone", "profile_completed")


    def update(self, instance, validated_data):
        profile_picture = validated_data.pop("profile_picture", None)

        if profile_picture:
            instance.profile_url = self.upload_profile_picture(
                profile_picture
            )
        return super().update(instance, validated_data)

    def upload_profile_picture(self, file):
        file_bytes = file.read()
        base, ext = os.path.splitext(file.name or "file")
        unique_name = f"{base}_{uuid.uuid4().hex}{ext}"
        key = f"profile_pictures/{unique_name}"

        supabase.storage.from_("marketplace").upload(
            key,
            file_bytes,
            {"content-type": file.content_type},
        )

        return supabase.storage.from_("marketplace").get_public_url(key)

# class UserProfileSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = UserProfile
#         fields = ['user', 'role']        



class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = User.objects.get(pk=self.user.id)
        serializer= UserSerializer(user)
        data.update(
            {'user': serializer.data})
        return data
