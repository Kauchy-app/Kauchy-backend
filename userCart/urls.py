from django.urls import path
from .views import CarItemView, GetCartItemView

urlpatterns = [
    path('cart-items/', GetCartItemView.as_view(), name='cart-items'),
    # path('cart-items/add', CarItemView.as_view(), name='cart-item-add'),
    # delete a specific cart item by its PK: DELETE /cart/cart-items/<pk>/
    path('cart-items/<int:pk>', CarItemView.as_view(), name='cart-item-detail'),
]