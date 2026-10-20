from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.serializers import (
    CreateUserSerializer,
    CurrentUserSerializer,
    DeleteAccountSerializer,
    LoginSerializer,
    UserSettingsSerializer,
)


DIRMILE_AUTH_BACKEND = "accounts.backends.DirmileAuthBackend"

UNAUTHENTICATED_DETAIL = "Authentication credentials were not provided."


def _unauthenticated_response():
    return Response(
        {"detail": UNAUTHENTICATED_DETAIL},
        status=status.HTTP_401_UNAUTHORIZED,
    )


def _require_authenticated_user(request):
    """
    Return (user, None) when authenticated.

    Return (None, 401 Response) when not authenticated.

    This avoids relying on DRF permission-denied mapping, which can
    return 403 instead of 401 depending on authentication state.
    """

    user = getattr(request, "user", None)

    if user is None:
        return None, _unauthenticated_response()

    is_authenticated = getattr(user, "is_authenticated", False)
    is_active = getattr(user, "is_active", True)

    if not is_authenticated or not is_active:
        return None, _unauthenticated_response()

    return user, None


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_token_view(request):
    """
    Returns a CSRF token and ensures the csrftoken cookie is set.

    The React frontend will call this before authenticated POST/PATCH/DELETE
    requests when using session authentication.
    """

    token = get_token(request)
    return Response({"csrf_token": token})


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    serializer = CreateUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = serializer.save()

    login(request, user, backend=DIRMILE_AUTH_BACKEND)

    return Response(
        CurrentUserSerializer(user).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    identifier = serializer.validated_data["identifier"].strip()
    password = serializer.validated_data["password"]

    user = authenticate(
        request,
        username=identifier,
        password=password,
    )

    if user is None:
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    login(request, user, backend=DIRMILE_AUTH_BACKEND)

    return Response(CurrentUserSerializer(user).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    user, auth_response = _require_authenticated_user(request)

    if auth_response is not None:
        return auth_response

    logout(request)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([AllowAny])
def me_view(request):
    user, auth_response = _require_authenticated_user(request)

    if auth_response is not None:
        return auth_response

    return Response(CurrentUserSerializer(user).data)


@api_view(["PATCH"])
@permission_classes([AllowAny])
def account_settings_view(request):
    user, auth_response = _require_authenticated_user(request)

    if auth_response is not None:
        return auth_response

    serializer = UserSettingsSerializer(
        user,
        data=request.data,
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response(CurrentUserSerializer(user).data)


@api_view(["DELETE"])
@permission_classes([AllowAny])
def account_delete_view(request):
    user, auth_response = _require_authenticated_user(request)

    if auth_response is not None:
        return auth_response

    serializer = DeleteAccountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    password = serializer.validated_data["password"]

    if not user.check_password(password):
        raise ValidationError({"password": ["Incorrect password."]})

    logout(request)
    user.delete()

    return Response(status=status.HTTP_204_NO_CONTENT)
