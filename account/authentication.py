from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.core.exceptions import ValidationError

class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication to gracefully handle invalid UUIDs in tokens.
    SimpleJWT normally crashes with a 500 error if the user_id in the token 
    cannot be parsed as a UUID (e.g. old tokens or tokens from other apps).
    """
    def get_user(self, validated_token):
        try:
            return super().get_user(validated_token)
        except (ValueError, ValidationError):
            raise InvalidToken("Token contained an invalid user ID format.")
