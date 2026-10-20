import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import User

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9._-]{3,150}$")


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "name",
            "email",
            "username",
            "password",
            "confirm_password",
            "country_code",
            "phone",
            "otp_enabled",
        ]
        extra_kwargs = {
            "name": {"required": True, "allow_blank": False},
            "email": {"required": True},
            "username": {"required": True},
            "country_code": {"required": False, "allow_blank": True},
            "phone": {"required": False, "allow_blank": True},
            "otp_enabled": {"required": False},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value

    def validate_username(self, value):
        value = value.strip().lower()
        if not USERNAME_REGEX.match(value):
            raise serializers.ValidationError(
                "Username must be 3-150 characters and may contain letters, "
                "numbers, dot, hyphen, or underscore."
            )
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this username already exists."
            )
        return value

    def validate_phone(self, value):
        if value in (None, ""):
            return ""
        value = value.strip()
        if len(value) > 32:
            raise serializers.ValidationError("Phone number is too long.")
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.pop("confirm_password", None)
        if password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": ["Passwords do not match."]}
            )
        temp_user = User(
            email=attrs.get("email", ""),
            username=attrs.get("username", ""),
            name=attrs.get("name", ""),
        )
        validate_password(password, user=temp_user)
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password", None)
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "username",
            "country_code",
            "phone",
            "phone_verified",
            "otp_enabled",
            "preferred_interval_miles",
            "default_load_lb",
            "theme",
            "heatmap_metric",
            "map_style",
            "is_staff",
            "is_active",
            "date_joined",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "name",
            "country_code",
            "phone",
            "preferred_interval_miles",
            "default_load_lb",
            "theme",
            "heatmap_metric",
            "map_style",
        ]
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
            "country_code": {"required": False, "allow_blank": True},
            "phone": {"required": False, "allow_blank": True},
            "preferred_interval_miles": {"required": False},
            "default_load_lb": {"required": False},
            "theme": {"required": False},
            "heatmap_metric": {"required": False},
            "map_style": {"required": False},
        }

    def validate_phone(self, value):
        if value in (None, ""):
            return ""
        value = value.strip()
        if len(value) > 32:
            raise serializers.ValidationError("Phone number is too long.")
        return value


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    confirmation = serializers.CharField()

    def validate_confirmation(self, value):
        if value != "DELETE":
            raise serializers.ValidationError(
                'Type DELETE exactly to confirm account deletion.'
            )
        return value
