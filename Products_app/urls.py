from django.urls import path
from .views import *

urlpatterns = [
    path('', AllProductsView.as_view(), name='list-products'),
    path("my_products/", ProductListCreateView.as_view(), name="user-products"),
    path('create', CreateProductView.as_view(), name='create-product'),
    path('<uuid:pk>', ProductDetailView.as_view(), name ='product-detail'),
    path('<uuid:pk>/like/', ProductLikeToggleView.as_view(), name='toggle-product-like'),
    path('<uuid:pk>/reviews/', ProductReviewListCreateView.as_view(), name='product-reviews'),
    path('vendor-products/<uuid:pk>', GetVendorProducts.as_view(), name='Get vendor products'),
    
    # Product Requests
    path('requests/', ProductRequestListView.as_view(), name='product-requests-list'),
    path('requests/<uuid:pk>/', ProductRequestDetailView.as_view(), name='product-requests-detail'),
    path('requests/<uuid:pk>/respond/', ProductRequestResponseView.as_view(), name='product-requests-respond'),
]