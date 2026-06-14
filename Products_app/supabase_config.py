from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from supabase import create_client, Client


supabase_url: str = settings.SUPABASE_URL
supabase_secret: str = settings.SUPABASE_SECRET

# Validate configuration early so failures are explicit instead of raising
# low-level network errors during requests.
if not supabase_url:
	raise ImproperlyConfigured("SUPABASE_URL is not set. Please set SUPABASE_URL in your environment or .env file")

if not supabase_secret:
	raise ImproperlyConfigured("SUPABASE_SECRET is not set. Please set SUPABASE_SECRET in your environment or .env file")

supabase: Client = create_client(supabase_url, supabase_secret)