from django.urls import path
from .views import TrackProductView, TrackContentView, RecentVideosWatchedView, SearchSuggestionsView, SaveSearchQueryView, UserViewHistoryView


urlpatterns = [
    path('track/product/', TrackProductView.as_view(), name='track-product-view'),
    path('track/content/', TrackContentView.as_view(), name='track-content-view'),
    path('videos/recent/', RecentVideosWatchedView.as_view(), name='recent-videos'),
    path('suggestions/', SearchSuggestionsView.as_view(), name='search-suggestions'),
    path('search/', SaveSearchQueryView.as_view(), name='save-search'),
    path('history/', UserViewHistoryView.as_view(), name='view-history'),
]