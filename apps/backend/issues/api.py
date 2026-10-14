"""Issue detail (spec: issue-matching). Only issues relevant to one of the requesting user's
recommendations are visible; anything else is 404."""

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses
from developers.models import DeveloperSkill

from .models import RecommendedIssue
from .serializers import IssueDetailSerializer


class IssueDetailView(APIView):
    @extend_schema(
        operation_id="issues_retrieve",
        responses={200: IssueDetailSerializer, **error_responses(401, 404)},
    )
    def get(self, request: Request, pk: int) -> Response:
        user = current_user(request)
        relevant = (
            RecommendedIssue.objects.filter(issue_id=pk, recommendation__developer__user=user)
            .select_related("issue__repository", "recommendation__repository")
            .order_by("recommendation__rank", "rank")
            .first()
        )
        if relevant is None:
            raise NotFound()
        skills = set(
            DeveloperSkill.objects.filter(profile__user=user, confidence__gt=0).values_list(
                "skill__slug", flat=True
            )
        )
        serializer = IssueDetailSerializer(relevant, context={"developer_skills": skills})
        return Response(serializer.data)
