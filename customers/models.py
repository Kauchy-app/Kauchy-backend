import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


class TopCustomers(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    total_purchases = models.PositiveBigIntegerField()

    def __str__(self):
        return f"{self.customer} - {self.total_purchases}"
    
class TopVendors(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(User, on_delete=models.CASCADE)
    total_sales = models.PositiveBigIntegerField()

    def __str__(self):
        return f"{self.vendor} - {self.total_sales}"
    

class VendorProfiles(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    followers_count = models.PositiveIntegerField(default=0)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.email}"
    



class Follow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'vendor')
        ordering = ['-created_at']

    def clean(self):
        # Vendor must have vendor role
        if self.vendor.role != 'vendor':
            raise ValidationError("You can only follow vendors")
        # Cannot follow yourself
        if self.follower == self.vendor:
            raise ValidationError("You cannot follow yourself")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        # Update followers count
        profile = VendorProfiles.objects.get(user=self.vendor)
        profile.followers_count = self.vendor.followers.count()
        profile.save()

    def delete(self, *args, **kwargs):
        vendor = self.vendor
        super().delete(*args, **kwargs)
        # Update followers count
        profile = VendorProfiles.objects.get(user=vendor)
        profile.followers_count = vendor.followers.count()
        profile.save()

    def __str__(self):
        return f"{self.follower.email} follows {self.vendor.email}"

