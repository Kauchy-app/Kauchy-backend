#!/usr/bin/env python3
"""
WebSocket Configuration Diagnostic Tool
Run this to verify your WebSocket setup
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Pymarket.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.conf import settings
import importlib

def print_status(label, status, details=""):
    icon = "✓" if status else "✗"
    color = "\033[92m" if status else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{icon}{reset} {label}")
    if details:
        print(f"  {details}")

print("=" * 60)
print("WebSocket Configuration Diagnostic")
print("=" * 60)
print()

# Check ASGI application
print("1. ASGI Configuration:")
asgi_app = getattr(settings, 'ASGI_APPLICATION', None)
print_status(
    "ASGI_APPLICATION set",
    bool(asgi_app),
    f"Value: {asgi_app}"
)

# Check if daphne is installed
print("\n2. Installed Apps:")
installed_apps = settings.INSTALLED_APPS
print_status(
    "'daphne' in INSTALLED_APPS",
    'daphne' in installed_apps,
    f"Position: {installed_apps.index('daphne') if 'daphne' in installed_apps else 'Not found'}"
)
print_status(
    "'channels' in INSTALLED_APPS",
    'channels' in installed_apps
)

# Check Channel Layers
print("\n3. Channel Layers:")
channel_layers = getattr(settings, 'CHANNEL_LAYERS', None)
if channel_layers:
    backend = channel_layers.get('default', {}).get('BACKEND', '')
    print_status(
        "CHANNEL_LAYERS configured",
        bool(backend),
        f"Backend: {backend}"
    )
    
    # Check Redis URL
    redis_config = channel_layers.get('default', {}).get('CONFIG', {})
    redis_hosts = redis_config.get('hosts', [])
    redis_url = redis_hosts[0] if redis_hosts else None
    print_status(
        "Redis URL configured",
        bool(redis_url),
        f"URL: {redis_url if redis_url else 'Not set'}"
    )
else:
    print_status("CHANNEL_LAYERS configured", False, "Not configured!")

# Check routing
print("\n4. WebSocket Routing:")
try:
    import chatapp.routing
    patterns = chatapp.routing.websocket_urlpatterns
    print_status(
        "chatapp.routing exists",
        True,
        f"Found {len(patterns)} pattern(s)"
    )
    for i, pattern in enumerate(patterns, 1):
        print(f"  Pattern {i}: {pattern.pattern.pattern}")
except Exception as e:
    print_status("chatapp.routing exists", False, str(e))

# Check consumer
print("\n5. WebSocket Consumer:")
try:
    from chatapp.consumer import UnifiedChatConsumer
    print_status("UnifiedChatConsumer imported", True)
except Exception as e:
    print_status("UnifiedChatConsumer imported", False, str(e))

# Check middleware
print("\n6. JWT Middleware:")
try:
    from chatapp.middleware import JWTAuthMiddleware
    print_status("JWTAuthMiddleware imported", True)
except Exception as e:
    print_status("JWTAuthMiddleware imported", False, str(e))

# Check CORS/Security
print("\n7. CORS Configuration:")
cors_allow_all = getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False)
print_status(
    "CORS_ALLOW_ALL_ORIGINS",
    cors_allow_all,
    "Enabled" if cors_allow_all else "Disabled"
)

allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
print_status(
    "ALLOWED_HOSTS configured",
    bool(allowed_hosts),
    f"Hosts: {allowed_hosts}"
)

# Environment variables check
print("\n8. Required Environment Variables:")
env_vars = {
    'SECRET_KEY': bool(os.environ.get('SECRET_KEY')),
    'REDIS_URL': bool(os.environ.get('REDIS_URL')),
}

for var, status in env_vars.items():
    print_status(f"{var} set", status)

print()
print("=" * 60)
print("Diagnostic Complete")
print("=" * 60)

# Summary
issues = []
if not asgi_app:
    issues.append("ASGI_APPLICATION not configured")
if 'daphne' not in installed_apps:
    issues.append("daphne not in INSTALLED_APPS")
if not channel_layers:
    issues.append("CHANNEL_LAYERS not configured")
if not env_vars.get('REDIS_URL'):
    issues.append("REDIS_URL environment variable not set")

if issues:
    print("\n⚠️  Issues Found:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("\n✓ All checks passed! WebSocket should work.")
    print("\nTo test locally, run:")
    print("  python3 manage.py runserver")
    print("\nThen open browser console and try:")
    print("  const ws = new WebSocket('ws://127.0.0.1:8000/ws/chat?token=YOUR_TOKEN');")
