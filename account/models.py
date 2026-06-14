from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.db import models
from django.contrib.auth.models import AbstractUser

VENDOR = "vendor"
BUYER = "buyer"

ROLE_CHOICES = [
    (VENDOR, "vendor"),
    (BUYER, "buyer"),
]


class CustomUserModel(AbstractUser):
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    institute = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20)
    rating = models.PositiveIntegerField(default=0)
    profile_url = models.TextField(null=True, default="https://icuklzexzhusblkzglnr.supabase.co/storage/v1/object/public/marketplace/profiie_pictures/freepik__adjust__23179.png")
    bio = models.TextField(null=True, blank=True)
    online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    # False until a social (Google) sign-up completes the fields Google can't
    # provide (phone, institute, role). Normal email/password signups set this
    # True at creation. Kept separate from is_active so JWT auth still works
    # while the profile is incomplete.
    profile_completed = models.BooleanField(default=False)
    


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
