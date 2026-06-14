from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


class TopCustomers(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    total_purchases = models.PositiveBigIntegerField()

    def __str__(self):
        return f"{self.customer} - {self.total_purchases}"
    
class TopVendors(models.Model):
    vendor = models.ForeignKey(User, on_delete=models.CASCADE)
    total_sales = models.PositiveBigIntegerField()

    def __str__(self):
        return f"{self.vendor} - {self.total_sales}"
    

class VendorProfiles(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    followers_count = models.PositiveIntegerField(default=0)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.email}"
    

class VendorContents(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='videos')
    video = models.URLField(max_length=500, blank=True, null=True)  # Changed to URLField
    pictures = models.URLField(max_length=500, blank=True, null=True)  # Changed to URLField
    caption = models.TextField(blank=True, null=True)
    likes_count = models.PositiveIntegerField(default=0)
    reviews_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.video and self.pictures:
            raise ValidationError("You can only upload either a video or pictures, not both.")
        if not self.video and not self.pictures:
            raise ValidationError("You must upload either a video or pictures.")
        
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "User Content"
        verbose_name_plural = "User Contents"
        ordering = ['-uploaded_at']

    def __str__(self):
        content_type = 'Video' if self.video else 'Picture'
        return f"{content_type} by {self.user.email} uploaded at {self.uploaded_at}"


class Follow(models.Model):
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


class ContentLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='content_likes')
    content = models.ForeignKey(VendorContents, on_delete=models.CASCADE, related_name='content_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'content')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update likes count
        self.content.likes_count = self.content.content_likes.count()
        self.content.save()

    def delete(self, *args, **kwargs):
        content = self.content
        super().delete(*args, **kwargs)
        # Update likes count
        content.likes_count = content.content_likes.count()
        content.save()

    def __str__(self):
        return f"{self.user.email} likes content {self.content.id}"


class ContentReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='content_reviews')
    content = models.ForeignKey(VendorContents, on_delete=models.CASCADE, related_name='content_reviews')
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # unique_together = ('user', 'content')
        ordering = ['-created_at']

    def clean(self):
        # Only buyers can review
        if self.user.role != 'buyer':
            raise ValidationError("Only buyers can review vendor content")
        # Cannot review your own content
        if self.user == self.content.user:
            raise ValidationError("You cannot review your own content")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        # Update reviews count
        self.content.reviews_count = self.content.content_reviews.count()
        self.content.save()

    def delete(self, *args, **kwargs):
        content = self.content
        super().delete(*args, **kwargs)
        # Update reviews count
        content.reviews_count = content.content_reviews.count()
        content.save()

    def __str__(self):
        return f"{self.user.email} reviewed content {self.content.id}"