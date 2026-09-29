from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses
from services.jobs import (
    SYNC,
    GitHubNotConnected,
    SyncCooldown,
    last_completed,
    start_profile_sync,
)

from .models import SyncJob
from .serializers import SyncJobSerializer, SyncStatusSerializer


class GitHubNotConnectedError(APIException):
    status_code = 409
    default_code = "github_not_connected"
    default_detail = "Connect your GitHub account to sync."


class SyncCooldownError(APIException):
    status_code = 429
    default_code = "sync_cooldown"
    default_detail = "A sync ran recently. Try again later."

    def __init__(self, retry_after: int) -> None:
        super().__init__()
        self.wait = retry_after


class StartSyncView(APIView):
    @extend_schema(
        operation_id="profile_sync_start",
        request=None,
        responses={202: SyncJobSerializer, **error_responses(401, 403, 409, 429)},
    )
    def post(self, request: Request) -> Response:
        try:
            job, _created = start_profile_sync(current_user(request))
        except GitHubNotConnected:
            raise GitHubNotConnectedError() from None
        except SyncCooldown as cooldown:
            raise SyncCooldownError(cooldown.retry_after) from None
        return Response(SyncJobSerializer(job).data, status=202)


class SyncStatusView(APIView):
    @extend_schema(
        operation_id="sync_status",
        responses={200: SyncStatusSerializer, **error_responses(401)},
    )
    def get(self, request: Request) -> Response:
        user = current_user(request)
        job = SyncJob.objects.filter(user=user, job_type=SYNC).order_by("-created_at").first()
        done = last_completed(user)
        return Response(
            SyncStatusSerializer(
                {"job": job, "last_synced_at": done.completed_at if done else None}
            ).data
        )
