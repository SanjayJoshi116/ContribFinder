from django.http import HttpRequest, JsonResponse


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    """CSRF_FAILURE_VIEW: same error envelope as the API instead of Django's HTML page."""
    return JsonResponse(
        {"error": {"code": "csrf_failed", "message": "CSRF verification failed."}},
        status=403,
    )


def not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    """handler404: JSON envelope for unmatched paths (active when DEBUG is False)."""
    return JsonResponse({"error": {"code": "not_found", "message": "Not found."}}, status=404)


def server_error(request: HttpRequest) -> JsonResponse:
    """handler500: JSON envelope without internals."""
    return JsonResponse(
        {"error": {"code": "server_error", "message": "An unexpected error occurred."}},
        status=500,
    )
