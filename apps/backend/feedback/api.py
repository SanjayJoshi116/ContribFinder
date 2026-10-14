"""Feedback, save and dismiss endpoints (spec: recommendation-feedback; design D4). Thin
wrappers around ``services.feedback``."""

from django.db.models import Prefetch, QuerySet
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses
from issues.models import RecommendedIssue
from recommendations.models import Recommendation
from repositories.models import RepositorySnapshot
from services import feedback

from .models import DismissedRepository, SavedRepository
from .serializers import (
    DismissedRepositorySerializer,
    FeedbackSerializer,
    SavedRepositorySerializer,
    SaveResultSerializer,
)

_NO_CONTENT = OpenApiResponse(description="Done.")


def _own_recommendation(request: Request, pk: int) -> Recommendation:
    """The requesting user's recommendation; 404 for anyone else's."""
    return get_object_or_404(
        Recommendation.objects.select_related("repository", "scoring_config"),
        pk=pk,
        developer__user=current_user(request),
    )


class FeedbackView(APIView):
    @extend_schema(
        operation_id="recommendations_feedback",
        request=FeedbackSerializer,
        responses={204: _NO_CONTENT, **error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, pk: int) -> Response:
        recommendation = _own_recommendation(request, pk)
        body = FeedbackSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        issue = None
        if (issue_id := body.validated_data.get("issue_id")) is not None:
            relevant = (
                RecommendedIssue.objects.filter(recommendation=recommendation, issue_id=issue_id)
                .select_related("issue")
                .first()
            )
            if relevant is None:
                raise ValidationError({"issue_id": "Not a relevant issue of this recommendation."})
            issue = relevant.issue
        feedback.record(
            current_user(request), recommendation, body.validated_data["action"], issue=issue
        )
        return Response(status=204)


class SaveView(APIView):
    @extend_schema(
        operation_id="recommendations_save",
        request=None,
        responses={200: SaveResultSerializer, **error_responses(401, 403, 404)},
    )
    def post(self, request: Request, pk: int) -> Response:
        feedback.save(current_user(request), _own_recommendation(request, pk))
        return Response(SaveResultSerializer({"saved": True}).data)

    @extend_schema(
        operation_id="recommendations_unsave",
        responses={200: SaveResultSerializer, **error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, pk: int) -> Response:
        recommendation = _own_recommendation(request, pk)
        feedback.unsave(current_user(request), recommendation.repository_id)
        return Response(SaveResultSerializer({"saved": False}).data)


class DismissView(APIView):
    @extend_schema(
        operation_id="recommendations_dismiss",
        request=None,
        responses={204: _NO_CONTENT, **error_responses(401, 403, 404)},
    )
    def post(self, request: Request, pk: int) -> Response:
        feedback.dismiss(current_user(request), _own_recommendation(request, pk))
        return Response(status=204)


class FeedbackPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class SavedListView(ListAPIView[SavedRepository]):
    """Saved repositories, most recently saved first, whether or not still recommended."""

    serializer_class = SavedRepositorySerializer
    pagination_class = FeedbackPagination
    filter_backends = []

    def get_queryset(self) -> QuerySet[SavedRepository]:
        if getattr(self, "swagger_fake_view", False):  # schema generation: no request user
            return SavedRepository.objects.none()
        user = current_user(self.request)
        return (
            SavedRepository.objects.filter(user=user)
            .select_related("repository")
            .prefetch_related(
                "repository__topics",
                Prefetch(
                    "repository__snapshots",
                    queryset=RepositorySnapshot.objects.order_by("-captured_at", "-pk"),
                    to_attr="ordered_snapshots",
                ),
                Prefetch(
                    "repository__recommendations",
                    queryset=Recommendation.objects.filter(developer__user=user).prefetch_related(
                        "reasons"
                    ),
                    to_attr="user_recommendations",
                ),
            )
            .order_by("-saved_at", "-pk")
        )

    @extend_schema(
        operation_id="saved_list",
        responses={200: SavedRepositorySerializer(many=True), **error_responses(401)},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)


class SavedDetailView(APIView):
    @extend_schema(
        operation_id="saved_delete",
        responses={204: _NO_CONTENT, **error_responses(401, 403)},
    )
    def delete(self, request: Request, repository_id: int) -> Response:
        feedback.unsave(current_user(request), repository_id)
        return Response(status=204)


class DismissedListView(ListAPIView[DismissedRepository]):
    """Hidden repositories, most recently dismissed first."""

    serializer_class = DismissedRepositorySerializer
    pagination_class = FeedbackPagination
    filter_backends = []

    def get_queryset(self) -> QuerySet[DismissedRepository]:
        if getattr(self, "swagger_fake_view", False):
            return DismissedRepository.objects.none()
        return (
            DismissedRepository.objects.filter(user=current_user(self.request))
            .select_related("repository")
            .prefetch_related("repository__topics")
            .order_by("-dismissed_at", "-pk")
        )

    @extend_schema(
        operation_id="dismissed_list",
        responses={200: DismissedRepositorySerializer(many=True), **error_responses(401)},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)


class DismissedDetailView(APIView):
    @extend_schema(
        operation_id="dismissed_restore",
        responses={204: _NO_CONTENT, **error_responses(401, 403)},
    )
    def delete(self, request: Request, repository_id: int) -> Response:
        feedback.restore(current_user(request), repository_id)
        return Response(status=204)
