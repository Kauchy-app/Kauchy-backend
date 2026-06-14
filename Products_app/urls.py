from django.urls import path
from .views import *

urlpatterns = [
    path('', AllProductsView.as_view(), name='list-products'),
    path("my_products/", ProductListCreateView.as_view(), name="user-products"),
    path('create', CreateProductView.as_view(), name='create-product'),
    path('<int:pk>', ProductDetailView.as_view(), name ='product-detail'),
    path('<int:pk>/like/', ProductLikeToggleView.as_view(), name='toggle-product-like'),
    path('<int:pk>/reviews/', ProductReviewListCreateView.as_view(), name='product-reviews'),
    path('vendor-products/<int:pk>', GetVendorProducts.as_view(), name='Get vendor products')
]