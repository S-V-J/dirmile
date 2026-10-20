from rest_framework.authentication import SessionAuthentication


class DirmileSessionAuthentication(SessionAuthentication):
    """
    Session authentication for Dirmile.

    This class:
    - returns None for anonymous/unauthenticated users
    - returns None for inactive users
    - enforces CSRF for authenticated unsafe requests
    """

    def authenticate(self, request):
        user = getattr(request._request, "user", None)

        if user is None:
            return None

        is_authenticated = getattr(user, "is_authenticated", False)
        is_active = getattr(user, "is_active", True)

        if not is_authenticated or not is_active:
            return None

        self.enforce_csrf(request)

        return (user, None)
