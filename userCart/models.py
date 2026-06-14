from django.db import models
from Products_app.models import Product
from django.contrib.auth import get_user_model
User = get_user_model()


class CartItem(models.Model):
    user=models.ForeignKey(User, on_delete=models.CASCADE)
    product=models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)