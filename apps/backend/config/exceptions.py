"""Single JSON error envelope for every /api/v1 error response.

{"error": {"code": "<stable_code>", "message": "<human text>", "details": {...}?}}
"""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

logger = logging.getLogger(__name__)

_CODE_BY_EXCEPTION: tuple[tuple[type[exceptions.APIException], str], ...] = (
    (exceptions.ValidationError, "validation_error"),
    (exceptions.NotAuthenticated, "not_authenticated"),
    (exceptions.AuthenticationFailed, "not_authenticated"),
    (exceptions.Throttled, "throttled"),
    (exceptions.NotFound, "not_found"),
    (exceptions.MethodNotAllowed, "method_not_allowed"),
    (exceptions.ParseError, "parse_error"),
    (exceptions.UnsupportedMediaType, "unsupported_media_type"),
    (exceptions.PermissionDenied, "permission_denied"),
)


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def _code_for(exc: exceptions.APIException) -> str:
    if isinstance(exc, exceptions.PermissionDenied) and str(exc.detail).startswith("CSRF Failed"):
        return "csrf_failed"
    if isinstance(exc, exceptions.ValidationError):
        return "validation_error"
    # Exact type only: application subclasses (e.g. NotSynced(NotFound)) keep their own
    # default_code instead of inheriting the generic one.
    for exc_type, code in _CODE_BY_EXCEPTION:
        if type(exc) is exc_type:
            return code
    return str(exc.default_code)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None or not isinstance(exc, exceptions.APIException):
        logger.exception("Unhandled API error", exc_info=exc)
        set_rollback()
        return Response(error_body("server_error", "An unexpected error occurred."), status=500)

    code = _code_for(exc)
    if isinstance(exc, exceptions.ValidationError):
        body = error_body(code, "Invalid input.", response.data)
    elif code == "csrf_failed":
        body = error_body(code, "CSRF verification failed.")
    else:
        body = error_body(code, str(exc.detail))
    response.data = body
    return response
