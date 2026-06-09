from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for InteractorGate AAC app.
    Extends AbstractUser to allow future AAC-specific fields.
    """

    class Meta:
        db_table = "users_user"
