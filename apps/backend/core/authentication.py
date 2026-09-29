from typing import TYPE_CHECKING

from rest_framework import authentication
from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request

if TYPE_CHECKING:
    from accounts.models import User


class SessionAuthentication(authentication.SessionAuthentication):
    """Session auth that makes DRF answer 401 (not 403) for unauthenticated requests.

    DRF only uses 401 when the first authenticator provides a WWW-Authenticate value.
    """

    def authenticate_header(self, request: Request) -> str:
        return 'Session realm="api"'


def current_user(request: Request) -> "User":
    """The authenticated application user; NotAuthenticated otherwise (never an assert)."""
    from accounts.models import User

    user = request.user
    if not isinstance(user, User):
        raise NotAuthenticated()
    return user
