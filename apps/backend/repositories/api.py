"""Discovery status and candidate pool (Phase 4). Stored data only: never calls GitHub."""

from typing import Any

from django.conf import settings
from django.db.models import (
    Case,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses
from jobs.models import SyncJob
from services.discovery.ordering import pool_order
from services.jobs import DISCOVERY, last_completed

from .models import (
    ActivityLabel,
    CandidateDiscovery,
    DiscoverySource,
    RepositoryCandidate,
    RepositorySnapshot,
)
from .queries import SNAPSHOT_NEWEST_FIRST, with_current_activity
from .serializers import DiscoveryStatusSerializer, RepositoryCandidateSerializer


class DiscoveryStatusView(APIView):
    @extend_schema(
        operation_id="discovery_status",
        responses={200: DiscoveryStatusSerializer, **error_responses(401)},
    )
    def get(self, request: Request) -> Response:
        user = current_user(request)
        job = SyncJob.objects.filter(user=user, job_type=DISCOVERY).order_by("-created_at").first()
        done = last_completed(user, DISCOVERY)
        pool = RepositoryCandidate.objects.filter(developer__user=user)
        counts = pool.aggregate(
            total=Count("pk"),
            eligible=Count("pk", filter=Q(repository__is_eligible=True)),
            awaiting_analysis=Count("pk", filter=Q(repository__is_eligible__isnull=True)),
            ineligible=Count("pk", filter=Q(repository__is_eligible=False)),
        )
        by_source = dict(
            CandidateDiscovery.objects.filter(candidate__developer__user=user)
            .values_list("source")
            .annotate(n=Count("candidate", distinct=True))
            .values_list("source", "n")
        )
        return Response(
            DiscoveryStatusSerializer(
                {
                    "job": job,
                    "last_completed_at": done.completed_at if done else None,
                    "pool": {**counts, "by_source": by_source},
                }
            ).data
        )


class CandidatePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


# django-filter ships no type information.
class CandidateFilter(filters.FilterSet):  # type: ignore[misc]
    source = filters.ChoiceFilter(choices=DiscoverySource.choices, method="filter_source")
    eligible = filters.BooleanFilter(field_name="repository__is_eligible")
    activity = filters.ChoiceFilter(choices=ActivityLabel.choices, field_name="activity_label")

    class Meta:
        model = RepositoryCandidate
        fields = ["source", "eligible", "activity"]

    def filter_source(self, queryset: QuerySet[Any], name: str, value: str) -> QuerySet[Any]:
        found = CandidateDiscovery.objects.filter(candidate=OuterRef("pk"), source=value)
        return queryset.filter(Exists(found))


class CandidateListView(ListAPIView[RepositoryCandidate]):
    """The developer's candidate pool: analysed-eligible first, then awaiting analysis, then
    ineligible; within each, the order in which discovery keeps and analyzes them (previously
    interacted, best search rank, most recently found, name). Not a ranking."""

    serializer_class = RepositoryCandidateSerializer
    pagination_class = CandidatePagination
    filterset_class = CandidateFilter

    def get_queryset(self) -> QuerySet[RepositoryCandidate]:
        if getattr(self, "swagger_fake_view", False):  # schema generation: no request user
            return RepositoryCandidate.objects.none()
        # The label as of now under the current thresholds, as generation scores it (CR5-2).
        latest_label = with_current_activity(
            RepositorySnapshot.objects.filter(repository=OuterRef("repository")).order_by(
                *SNAPSHOT_NEWEST_FIRST
            ),
            timezone.now(),
            settings.ACTIVITY_THRESHOLDS,
        ).values("current_label")[:1]  # type: ignore[misc]  # annotated by the helper
        state = Case(
            When(repository__is_eligible=True, then=Value(0)),
            When(repository__is_eligible__isnull=True, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
        candidates = (
            RepositoryCandidate.objects.filter(developer__user=current_user(self.request))
            .select_related("repository")
            .prefetch_related("discoveries", "repository__topics")
            .annotate(activity_label=Subquery(latest_label), state=state)
        )
        return pool_order(candidates, "state")

    @extend_schema(
        operation_id="discovery_candidates",
        responses={200: RepositoryCandidateSerializer(many=True), **error_responses(401)},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)
