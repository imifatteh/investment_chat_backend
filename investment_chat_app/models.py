from django.contrib.auth.models import User
from django.db import models


class UserData(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_chats_sent = models.PositiveIntegerField(default=0)
    total_chats_received = models.PositiveIntegerField(default=0)
