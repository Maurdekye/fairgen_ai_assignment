from django.contrib.auth.models import AbstractUser
from django.db import models
from main.models import University

class User(AbstractUser):
    GROUP_CHOICES = (
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("personnel", "Personnel"),
        ("user", "User"),
    )
    university = models.ForeignKey(University, on_delete=models.SET_NULL, null=True, blank=True)
    group = models.CharField(max_length=20, choices=GROUP_CHOICES, default="user")