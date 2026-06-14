"""
URL configuration for Pymarket project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .utils import link_preview



def health_check(request):
    return HttpResponse("OK")


urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('admin/', admin.site.urls),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    path('auth/', include('account.urls')),
    path('products/', include('Products_app.urls')),
    path('cart/', include('userCart.urls')),
    path('payment/', include('paymentapp.urls')),
    path("wallet/",include("wallet.urls")),
    path("customers/",include("customers.urls")),
    path("search/",include("usersearch.urls")),
    path("health/", health_check),
    path('analytics/', include('analytics.urls')),
    path('chat/', include('chatapp.urls')),
    path('vendor-profile', link_preview),
    path('orders/', include('orders.urls')),
    path('waitlist/', include('waitlist.urls')),
    path('dispute/', include('dispute.urls')),
    path('kauch/', include('kauch.urls'))
]
