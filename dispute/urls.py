from django.urls import path
from .views import CreateDisputeView, GetDisputeView

urlpatterns = [
    path('', CreateDisputeView.as_view(), name='create-dispute'),
    path('all/', GetDisputeView.as_view(), name='get-dispute'),
]
