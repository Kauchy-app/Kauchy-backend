from django.db import models
from Products_app.models import Product
from django.contrib.auth import get_user_model
User = get_user_model()


# Create your models here.

class UserCategoryModel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user")
    category = models.CharField(max_length=100)
    view_count = models.PositiveIntegerField(default=1)


class UserVendorAffinity(models.Model):
    """How much a user gravitates toward a vendor, raised when the user LIKES
    that vendor's products or content (never on passive views). Used to boost
    the vendor's items in the personalized feed."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vendor_affinities")
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="affinity_from_users")
    score = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("user", "vendor")