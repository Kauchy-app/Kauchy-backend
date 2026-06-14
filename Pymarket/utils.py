from django.contrib.auth import get_user_model
from django.http import HttpResponse

User = get_user_model()

def link_preview(request):
    vendor_id = request.GET.get('vendorId')
    
    try:
        vendor_info = User.objects.get(id=vendor_id)
    except User.DoesNotExist:
        return HttpResponse("Vendor not found", status=404)
    
    # Check if pfp exists

    image_url = vendor_info.profile_url
    
    # Detect if it's a bot/scraper
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_bot = any(bot in user_agent for bot in [
        'facebookexternalhit', 'whatsapp', 'telegram', 'twitter', 
        'slack', 'discord', 'linkedinbot', 'pinterest'
    ])
    
    # Only redirect if it's NOT a bot
    redirect_meta = '' if is_bot else '<meta http-equiv="refresh" content="0;url=https://upstart-e9ry.onrender.com/vendor-profile.html?vendorId=' + vendor_id + '">'
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <!-- Open Graph (for WhatsApp, Facebook, etc.) -->
        <meta property="og:title" content="{vendor_info.username} Profile - Upstart">
        <meta property="og:description" content="{vendor_info.bio}">
        <meta property="og:image" content="{image_url}">
        <meta property="og:url" content="http://127.0.0.1:8000/vendor-profile?vendorId={vendor_id}">
        <meta property="og:type" content="profile">
        
        <!-- Twitter Card tags -->
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="{vendor_info.username} Profile - Upstart">
        <meta name="twitter:description" content="{vendor_info.bio}">
        <meta name="twitter:image" content="{image_url}">
        
        {redirect_meta}
    </head>
    <body>
        <p>Redirecting...</p>
    </body>
    </html>
    """
    
    return HttpResponse(html, content_type='text/html')