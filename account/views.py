from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import UserSerializer
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from paymentapp.models import Transaction, VendorWallet, BuyerWallet
from customers.models import VendorProfiles
from django.conf import settings
from django.db.models import Sum
import requests

User = get_user_model()

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def _issue_tokens(user):
    """Return the same payload shape as LoginSerializer (refresh/access/user)."""
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": UserSerializer(user).data,
    }


def _unique_username(base):
    """Derive a username that doesn't collide with an existing user."""
    base = (base or "user").split("@")[0]
    base = "".join(ch for ch in base if ch.isalnum() or ch in "._-") or "user"
    candidate = base[:150]
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base[:140]}{suffix}"
        suffix += 1
    return candidate


class GoogleAuthView(APIView):
    """Sign in / sign up with a Google ID token (credential from GIS).

    New users are created with the Google-provided email/name/picture and an
    incomplete profile (profile_completed=False); the frontend then prompts
    them to fill in phone/institute/role.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("id_token") or request.data.get("credential")
        if not token:
            return Response({"detail": "id_token is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Verify the token with Google.
        try:
            resp = requests.get(GOOGLE_TOKENINFO_URL, params={"id_token": token}, timeout=10)
        except requests.RequestException:
            return Response({"detail": "Could not reach Google to verify token."}, status=status.HTTP_502_BAD_GATEWAY)

        if resp.status_code != 200:
            return Response({"detail": "Invalid Google token."}, status=status.HTTP_401_UNAUTHORIZED)

        info = resp.json()

        if settings.GOOGLE_CLIENT_ID and info.get("aud") != settings.GOOGLE_CLIENT_ID:
            return Response({"detail": "Token audience mismatch."}, status=status.HTTP_401_UNAUTHORIZED)

        if str(info.get("email_verified")).lower() != "true":
            return Response({"detail": "Google email is not verified."}, status=status.HTTP_401_UNAUTHORIZED)

        email = (info.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "Google token has no email."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = User(
                email=email,
                username=_unique_username(info.get("name") or email),
                role="",
                phone="",
                institute=None,
                profile_completed=False,
                is_active=True,
            )
            picture = info.get("picture")
            if picture:
                user.profile_url = picture
            user.set_unusable_password()
            user.save()

        return Response(_issue_tokens(user), status=status.HTTP_200_OK)


class CompleteProfileView(APIView):
    """Fill in the fields Google can't supply and activate the account fully."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        username = (request.data.get("username") or "").strip()
        phone = (request.data.get("phone") or "").strip()
        institute = (request.data.get("institute") or "").strip()
        role = (request.data.get("role") or "").strip().lower()

        errors = {}
        if not username:
            errors["username"] = "Username is required."
        elif User.objects.filter(username=username).exclude(pk=user.pk).exists():
            errors["username"] = "This username is already taken."
        if not phone:
            errors["phone"] = "Phone number is required."
        if not institute:
            errors["institute"] = "University is required."
        if role not in ("buyer", "vendor"):
            errors["role"] = "Role must be 'buyer' or 'vendor'."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        user.username = username
        user.phone = phone
        user.institute = institute
        user.role = role
        user.profile_completed = True
        user.save()

        # Provision wallet/profile by role (idempotent), mirroring signup.
        if role == "vendor":
            VendorWallet.objects.get_or_create(vendor=user, defaults={"balance": 0})
            VendorProfiles.objects.get_or_create(user=user)
        else:
            BuyerWallet.objects.get_or_create(user=user, defaults={"balance": 0})

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class GetUserProfile(APIView):
    def get(self, request, pk):
        try:
            data = User.objects.get(id=pk)
        except User.DoesNotExist:
            return Response({"message":"User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        vendor_tx_qs = Transaction.objects.filter(
            transaction_type='PURCHASE',
            status='COMPLETED',
            vendor__vendor=pk
        )
        total_sales_quantity = vendor_tx_qs.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        
        serializer = UserSerializer(data)
        response = {"info": serializer.data}
        response["sales"] = int(total_sales_quantity)
        # print(response)
        return Response(response, status=status.HTTP_200_OK)