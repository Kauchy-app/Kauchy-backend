from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

# Create your models here.

class Product(models.Model):
    vendor_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')
    product_name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10,decimal_places=2)
    quantity = models.PositiveIntegerField()
    category = models.CharField(max_length=255)
    image_url= models.JSONField(blank=True,null=True, default=list)
    # Optional, freeform vendor-defined attributes (e.g. {"Size": "M", "Colour": "Red"}).
    # Products differ wildly, so this is a flexible key/value bag rather than fixed columns.
    specs = models.JSONField(blank=True, default=dict)
    rating = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0, null=True,blank=True)
    likes_count = models.PositiveIntegerField(default=0)
    # rating = models.ForeignKey()
    
    


class ProductReviews(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer")
    rating = models.PositiveIntegerField()
    review = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class ProductView(models.Model):
    product =models.ForeignKey(Product, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')

class ProductLike(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.product.likes_count += 1
            self.product.save(update_fields=['likes_count'])

    def delete(self, *args, **kwargs):
        self.product.likes_count = max(0, self.product.likes_count - 1)
        self.product.save(update_fields=['likes_count'])
        super().delete(*args, **kwargs)
    
