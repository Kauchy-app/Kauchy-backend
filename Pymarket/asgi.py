# Pymarket/asgi.py

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Pymarket.settings')
django.setup()


from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async



# Initialize Django ASGI application early to ensure the AppRegistry is populated
# before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

import notification.routing
import chatapp.routing

from channels.db import database_sync_to_async

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_key):
    """Get user from JWT token"""
    try:
        decoded_data = AccessToken(token_key)
        user_id = decoded_data['user_id']
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()

class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = scope['query_string'].decode()
        token = None
        
        if 'token=' in query_string:
            token = query_string.split('token=')[1].split('&')[0]
        
        # Authenticate user
        scope['user'] = await get_user_from_token(token) if token else AnonymousUser()
        
        await super().__call__(scope, receive, send)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": TokenAuthMiddleware(
        URLRouter(
            chatapp.routing.websocket_urlpatterns +
            notification.routing.websocket_urlpatterns
        )
    ),
})
