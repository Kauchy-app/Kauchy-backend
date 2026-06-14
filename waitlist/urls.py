from django.urls import path
from .views import WaitlistViews


urlpatterns= [
    path('', WaitlistViews.as_view(), name='waitlist')
]