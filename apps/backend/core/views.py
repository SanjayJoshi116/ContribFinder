from django.http import HttpRequest, JsonResponse

from config.exceptions import error_body


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    """CSRF_FAILURE_VIEW: same error envelope as the API instead of Django's HTML page."""
    return JsonResponse(error_body("csrf_failed", "CSRF verification failed."), status=403)


def bad_request(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    """handler400: framework-level rejections (DisallowedHost, oversized body) as JSON."""
    return JsonResponse(error_body("bad_request", "Bad request."), status=400)


def permission_denied(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    """handler403: PermissionDenied raised outside DRF (DRF has its own envelope)."""
    return JsonResponse(error_body("permission_denied", "Permission denied."), status=403)


def not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    """handler404: JSON envelope for unmatched paths (active when DEBUG is False)."""
    return JsonResponse(error_body("not_found", "Not found."), status=404)


def server_error(request: HttpRequest) -> JsonResponse:
    """handler500: JSON envelope without internals."""
    return JsonResponse(error_body("server_error", "An unexpected error occurred."), status=500)
