from django.db import models
from django.contrib.auth import get_user_model

User= get_user_model()


class Notification(models.Model):
    NOTIFICATION_TYPES=[
        ('order','Order Update'),
        ('message','New Message'),
        ('payment','Payment Confirmation'),
        ('general','General Notification'),
        ('like','Like'),
        ('review','Review'),
        ('comment','Comment'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.email}: {self.message[:20]}..."
    
    class Meta:
        ordering = ['-created_at']


