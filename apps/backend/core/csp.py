"""Content-Security-Policy on every Django response (Django 5.2 has none built in).

JSON responses (the API) get ``CONTENT_SECURITY_POLICY_API``, which allows loading nothing; any
other response (the admin, error pages) gets ``CONTENT_SECURITY_POLICY_HTML``. A response that
already carries the header keeps it.
"""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponseBase

HEADER = "Content-Security-Policy"


def is_json(content_type: str) -> bool:
    """``application/json``, ``application/problem+json`` and the like, parameters ignored."""
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.endswith("/json") or media_type.endswith("+json")


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        response = self.get_response(request)
        if HEADER not in response:
            json = is_json(response.get("Content-Type", ""))
            response[HEADER] = (
                settings.CONTENT_SECURITY_POLICY_API
                if json
                else settings.CONTENT_SECURITY_POLICY_HTML
            )
        return response
