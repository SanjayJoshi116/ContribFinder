from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .health import HEALTHY, run_checks
from .serializers import HealthSerializer, error_responses


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="health",
        responses={200: HealthSerializer, 503: HealthSerializer, **error_responses(429)},
        auth=[],
    )
    def get(self, request: Request) -> Response:
        checks = run_checks()
        healthy = all(value in HEALTHY for value in checks.values())
        return Response(
            {"status": "ok" if healthy else "degraded", "checks": checks},
            status=200 if healthy else 503,
        )
