from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from accounts.models import User


class DirmileAuthBackend(ModelBackend):
    """
    Authenticate using email, username, or optional phone.

    The frontend may send the identifier in the `username` argument.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        if username is None or password is None:
            return None

        identifier = str(username).strip()

        if not identifier:
            return None

        user = (
            User.objects.filter(
                Q(email__iexact=identifier)
                | Q(username__iexact=identifier)
                | Q(phone=identifier)
            )
            .first()
        )

        if user is None:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
