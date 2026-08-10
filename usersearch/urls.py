from django.urls import path
from .views import TrackProductView, SearchSuggestionsView, SaveSearchQueryView, UserViewHistoryView


urlpatterns = [
    path('track/product/', TrackProductView.as_view(), name='track-product-view'),
    path('suggestions/', SearchSuggestionsView.as_view(), name='search-suggestions'),
    path('search/', SaveSearchQueryView.as_view(), name='save-search'),
    path('history/', UserViewHistoryView.as_view(), name='view-history'),
]