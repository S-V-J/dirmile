from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, username, password, **extra_fields):
        email = (email or "").strip()
        username = (username or "").strip()

        if not email:
            raise ValueError("Users must have an email address.")
        if not username:
            raise ValueError("Users must have a username.")

        email = self.normalize_email(email)

        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    INTERVAL_CHOICES = [
        (10, "10 miles"),
        (25, "25 miles"),
        (50, "50 miles"),
    ]

    THEME_CHOICES = [
        ("light", "Light"),
        ("dark", "Dark"),
        ("system", "System"),
    ]

    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)

    country_code = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    phone_verified = models.BooleanField(default=False)
    otp_enabled = models.BooleanField(default=False)

    preferred_interval_miles = models.PositiveSmallIntegerField(
        default=25,
        choices=INTERVAL_CHOICES,
    )
    default_load_lb = models.PositiveIntegerField(default=30000)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default="system")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.email or self.username
