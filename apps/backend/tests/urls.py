"""Test-only routes that exercise the API error envelope."""

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.urls import include, path
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.urls import (  # noqa: F401  (the real error handlers, not copies)
    handler400,
    handler403,
    handler404,
    handler500,
)
from config.urls import urlpatterns as app_urlpatterns
from core.throttling import AnonRateThrottle


class _EchoSerializer(serializers.Serializer[dict[str, object]]):
    name = serializers.CharField(max_length=5)


class ValidateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        s = _EchoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(s.validated_data)


class ProtectedView(APIView):
    def get(self, request: Request) -> Response:
        return Response({"ok": True})

    def post(self, request: Request) -> Response:
        return Response({"ok": True})


class _OnePerMinute(AnonRateThrottle):
    rate = "1/min"


class ThrottledView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [_OnePerMinute]

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class BoomView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request: Request) -> Response:
        raise RuntimeError("secret internal detail")


def denied_view(request: HttpRequest) -> HttpResponse:
    """A plain Django view (not DRF) that denies access."""
    raise PermissionDenied


test_api = [
    path("validate/", ValidateView.as_view()),
    path("protected/", ProtectedView.as_view()),
    path("throttled/", ThrottledView.as_view()),
    path("boom/", BoomView.as_view()),
    path("denied/", denied_view),
]

urlpatterns = [path("api/v1/_test/", include(test_api)), *app_urlpatterns]
