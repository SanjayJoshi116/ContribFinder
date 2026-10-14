"""Recommendation list, detail and status (spec: recommendations-view). Stored data only:
never calls GitHub, never recomputes scores."""

from typing import Any

from django.db.models import Exists, Max, OuterRef, Prefetch, QuerySet
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses
from feedback.models import SavedRepository
from issues.models import ContributionType, Difficulty, RecommendedIssue
from jobs.models import SyncJob
from repositories.models import ActivityLabel, RepositoryLanguage, RepositorySnapshot
from services.jobs import RECOMMENDATIONS
from services.profiling.taxonomy import LINGUIST_INDEX, SKILLS_BY_SLUG

from .models import MatchLabel, Recommendation, RepositorySize
from .serializers import (
    RecommendationDetailSerializer,
    RecommendationSerializer,
    RecommendationStatusSerializer,
)


class RecommendationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# django-filter ships no type information.
class RecommendationFilter(filters.FilterSet):  # type: ignore[misc]
    language = filters.ChoiceFilter(
        choices=sorted((name, name) for name in LINGUIST_INDEX),
        method="filter_language",
        help_text="Repositories with code in this language (case-insensitive), e.g. python.",
    )
    framework = filters.ChoiceFilter(
        choices=sorted((slug, slug) for slug in SKILLS_BY_SLUG),
        method="filter_framework",
        help_text="Catalog skill slug the repository uses, e.g. django or react.",
    )
    activity = filters.ChoiceFilter(choices=ActivityLabel.choices, field_name="activity_label")
    size = filters.ChoiceFilter(choices=RepositorySize.choices, field_name="size")
    match = filters.ChoiceFilter(choices=MatchLabel.choices, field_name="match_label")
    difficulty = filters.ChoiceFilter(
        choices=Difficulty.choices,
        method="filter_difficulty",
        help_text="At least one relevant issue of this estimated difficulty.",
    )
    contribution_type = filters.ChoiceFilter(
        choices=[c for c in ContributionType.choices if c[0] != ContributionType.UNKNOWN],
        method="filter_contribution_type",
        help_text="At least one relevant issue of this contribution type.",
    )

    class Meta:
        model = Recommendation
        fields = ["language", "framework", "activity", "size", "match"]

    def __init__(self, data: Any = None, *args: Any, **kwargs: Any) -> None:
        # Language names are case-insensitive; the choices are the lower-cased catalog names.
        if data is not None and "language" in data:
            data = data.copy()
            data["language"] = data["language"].lower()
        super().__init__(data, *args, **kwargs)

    def filter_language(self, queryset: QuerySet[Any], name: str, value: str) -> QuerySet[Any]:
        found = RepositoryLanguage.objects.filter(
            repository=OuterRef("repository"), language__iexact=value
        )
        return queryset.filter(Exists(found))

    def filter_framework(self, queryset: QuerySet[Any], name: str, value: str) -> QuerySet[Any]:
        return queryset.filter(technologies__contains=[{"slug": value}])

    def filter_difficulty(self, queryset: QuerySet[Any], name: str, value: str) -> QuerySet[Any]:
        return queryset.filter(issue_difficulties__contains=[value])

    def filter_contribution_type(
        self, queryset: QuerySet[Any], name: str, value: str
    ) -> QuerySet[Any]:
        return queryset.filter(issue_contribution_types__contains=[value])


def _user_recommendations(request: Request) -> QuerySet[Recommendation]:
    user = current_user(request)
    saved = SavedRepository.objects.filter(user=user, repository=OuterRef("repository"))
    return Recommendation.objects.filter(developer__user=user).annotate(saved=Exists(saved))


class RecommendationListView(ListAPIView[Recommendation]):
    """The user's recommendations, best first. No score or rank is exposed."""

    serializer_class = RecommendationSerializer
    pagination_class = RecommendationPagination
    filterset_class = RecommendationFilter

    def get_queryset(self) -> QuerySet[Recommendation]:
        if getattr(self, "swagger_fake_view", False):  # schema generation: no request user
            return Recommendation.objects.none()
        return (
            _user_recommendations(self.request)
            .select_related("repository")
            .prefetch_related("reasons", "repository__topics")
            .order_by("rank")
        )

    @extend_schema(
        operation_id="recommendations_list",
        responses={200: RecommendationSerializer(many=True), **error_responses(400, 401)},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)


class RecommendationDetailView(RetrieveAPIView[Recommendation]):
    serializer_class = RecommendationDetailSerializer

    def get_queryset(self) -> QuerySet[Recommendation]:
        if getattr(self, "swagger_fake_view", False):
            return Recommendation.objects.none()
        return (
            _user_recommendations(self.request)
            .select_related("repository", "repository__readme")
            .prefetch_related(
                "reasons",
                "repository__topics",
                "repository__languages",
                Prefetch(
                    "repository__snapshots",
                    queryset=RepositorySnapshot.objects.order_by("-captured_at", "-pk"),
                    to_attr="ordered_snapshots",
                ),
                Prefetch(
                    "recommended_issues",
                    queryset=RecommendedIssue.objects.select_related("issue").order_by("rank"),
                ),
            )
        )

    @extend_schema(
        operation_id="recommendations_retrieve",
        responses={200: RecommendationDetailSerializer, **error_responses(401, 404)},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)


class RecommendationStatusView(APIView):
    @extend_schema(
        operation_id="recommendations_status",
        responses={200: RecommendationStatusSerializer, **error_responses(401)},
    )
    def get(self, request: Request) -> Response:
        user = current_user(request)
        job = (
            SyncJob.objects.filter(user=user, job_type=RECOMMENDATIONS)
            .order_by("-created_at")
            .first()
        )
        recs = Recommendation.objects.filter(developer__user=user)
        latest = recs.select_related("scoring_config").order_by("-generated_at").first()
        return Response(
            RecommendationStatusSerializer(
                {
                    "job": job,
                    "last_generated_at": recs.aggregate(last=Max("generated_at"))["last"],
                    "count": recs.count(),
                    "config_version": latest.scoring_config.version if latest else None,
                }
            ).data
        )
