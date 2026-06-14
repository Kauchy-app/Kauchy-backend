from django.urls import path
from .views import GetAllOrders, ValidateOrderQRCodeView, VendorRespondOrderView

urlpatterns = [
    path('my_orders/', GetAllOrders.as_view(), name='my orders'),
    path('validate_order_qr/', ValidateOrderQRCodeView.as_view(), name='validate order qr'),
    path('respond/', VendorRespondOrderView.as_view(), name='respond_order'),
]