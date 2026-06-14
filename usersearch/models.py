from django.db import models
from django.conf import settings
from Products_app.models import Product
from customers.models import VendorContents

User = settings.AUTH_USER_MODEL


class ProductView(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_views')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='user_views')
    viewed_at = models.DateTimeField(auto_now_add=True)
    view_duration = models.PositiveIntegerField(default=0, help_text="Duration in seconds")
    
    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} viewed {self.product.product_name}"


class ContentView(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='content_views')
    content = models.ForeignKey(VendorContents, on_delete=models.CASCADE, related_name='user_views')
    viewed_at = models.DateTimeField(auto_now_add=True)
    view_duration = models.PositiveIntegerField(default=0, help_text="Duration in seconds")
    
    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} viewed content by {self.content.user.email}"


class SearchQuery(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_queries')
    query = models.CharField(max_length=255)
    searched_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-searched_at']
        verbose_name_plural = "Search Queries"
    
    def __str__(self):
        return f"{self.user.email} searched '{self.query}'"
