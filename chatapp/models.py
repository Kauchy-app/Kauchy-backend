from django.db import models
from django.contrib.auth import get_user_model
import uuid
User = get_user_model()

# Create your models here.


class ConversationModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="Vendor_id")
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="Buyer_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vendor', 'buyer')



class MessageModel(models.Model):
    conversation = models.ForeignKey(ConversationModel, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to="chat_files/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name='replies')

    class Meta:
        ordering = ["timestamp"]