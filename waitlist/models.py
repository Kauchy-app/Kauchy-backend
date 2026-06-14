from django.db import models

# Create your models here.


class WaitListModel(models.Model):
    email=models.EmailField(max_length=100, unique=True)