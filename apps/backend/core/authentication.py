from rest_framework import authentication
from rest_framework.request import Request


class SessionAuthentication(authentication.SessionAuthentication):
    """Session auth that makes DRF answer 401 (not 403) for unauthenticated requests.

    DRF only uses 401 when the first authenticator provides a WWW-Authenticate value.
    """

    def authenticate_header(self, request: Request) -> str:
        return 'Session realm="api"'
