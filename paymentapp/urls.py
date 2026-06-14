from django.urls import path
from .views import *


urlpatterns = [
    path('create-order/', InitializeOrderView.as_view(), name='create-order'),
]