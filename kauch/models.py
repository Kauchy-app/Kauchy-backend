from django.db import models
from django.conf import settings

# Create your models here.

User = settings.AUTH_USER_MODEL

MAX_KAUCHES_PER_VENDOR = 2


class KauchModel(models.Model):
    """A Kauch acts like a WhatsApp Channel. A vendor can own up to 2 Kauches."""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kauches')
    name = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(blank=True, default="")
    avatar_url = models.TextField(null=True, blank=True)
    followers_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (owner: {self.owner})"


class PostModel(models.Model):
    """A post within a Kauch containing text, media, and tagged products."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    MEDIA_TYPE_CHOICES = [
        (IMAGE, "image"),
        (VIDEO, "video"),
        (AUDIO, "audio"),
    ]

    kauch = models.ForeignKey(KauchModel, on_delete=models.CASCADE, related_name='posts')
    description = models.TextField(blank=True, default="")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default=IMAGE)
    # Single primary URL kept for backward compatibility (old posts, link previews).
    # For image posts this mirrors media_urls[0]; for video posts it is the video URL.
    media_url = models.TextField(null=True, blank=True)
    # Ordered list of media URLs. A post is either ONE video or MANY images, so this
    # holds [video_url] for video posts and [img1, img2, ...] for image posts.
    media_urls = models.JSONField(default=list, blank=True)
    tagged_products = models.ManyToManyField(
        'Products_app.Product', blank=True, related_name='kauch_posts'
    )
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    shares_count = models.PositiveIntegerField(default=0)
    bookmarks_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Post {self.pk} in {self.kauch.name}"


class PostLike(models.Model):
    post = models.ForeignKey(PostModel, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kauch_post_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.post.likes_count = self.post.likes.count()
            self.post.save(update_fields=['likes_count'])

    def delete(self, *args, **kwargs):
        post = self.post
        super().delete(*args, **kwargs)
        post.likes_count = post.likes.count()
        post.save(update_fields=['likes_count'])

    def __str__(self):
        return f"{self.user} likes post {self.post_id}"


class PostComment(models.Model):
    post = models.ForeignKey(PostModel, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kauch_post_comments')
    text = models.TextField()
    # A reply points at its parent comment; top-level comments have parent=None.
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.post.comments_count = self.post.comments.count()
            self.post.save(update_fields=['comments_count'])

    def delete(self, *args, **kwargs):
        post = self.post
        super().delete(*args, **kwargs)
        post.comments_count = post.comments.count()
        post.save(update_fields=['comments_count'])

    def __str__(self):
        return f"Comment {self.pk} by {self.user} on post {self.post_id}"


class Bookmark(models.Model):
    """A user saves (bookmarks) a post. Server-side so it syncs across devices."""
    post = models.ForeignKey(PostModel, on_delete=models.CASCADE, related_name='bookmarks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kauch_bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.post.bookmarks_count = self.post.bookmarks.count()
            self.post.save(update_fields=['bookmarks_count'])

    def delete(self, *args, **kwargs):
        post = self.post
        super().delete(*args, **kwargs)
        post.bookmarks_count = post.bookmarks.count()
        post.save(update_fields=['bookmarks_count'])

    def __str__(self):
        return f"{self.user} bookmarked post {self.post_id}"


class KauchFollow(models.Model):
    kauch = models.ForeignKey(KauchModel, on_delete=models.CASCADE, related_name='followers')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kauch_follows')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('kauch', 'user')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.kauch.followers_count = self.kauch.followers.count()
            self.kauch.save(update_fields=['followers_count'])

    def delete(self, *args, **kwargs):
        kauch = self.kauch
        super().delete(*args, **kwargs)
        kauch.followers_count = kauch.followers.count()
        kauch.save(update_fields=['followers_count'])

    def __str__(self):
        return f"{self.user} follows {self.kauch.name}"
