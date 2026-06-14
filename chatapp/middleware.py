# chatapp/middleware.py

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()


@database_sync_to_async
def get_user_from_jwt(token_string):
    """
    Decode JWT token and get user
    """
    try:
        # Decode the JWT token
        access_token = AccessToken(token_string)
        user_id = access_token['user_id']
        
        # Get user from database
        user = User.objects.get(id=user_id)
        return user
    except (InvalidToken, TokenError, User.DoesNotExist) as e:
        print(f"JWT Authentication failed: {e}")
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Custom middleware to authenticate WebSocket connections via JWT token.
    Token should be passed in query string: ?token=your_jwt_token
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        # Parse query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        # Get token from query string
        token = query_params.get('token', [None])[0]
        
        if token:
            # Authenticate user via JWT
            scope['user'] = await get_user_from_jwt(token)
        else:
            # No token provided
            scope['user'] = AnonymousUser()
        
        return await self.app(scope, receive, send)