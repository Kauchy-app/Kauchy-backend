import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# Create your models here.

class DisputeModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)