from django.db.models import Count, Prefetch, QuerySet
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses

from .models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    InterestEvidence,
    SkillCategory,
    SkillEvidence,
)
from .serializers import (
    DeveloperInterestSerializer,
    DeveloperProfileSerializer,
    DeveloperSkillSerializer,
)


class NotAnalyzed(NotFound):
    default_code = "not_analyzed"
    default_detail = "Your developer profile has not been built yet."


class DeveloperProfileView(APIView):
    """The analyzed developer profile. Stored data only: never calls GitHub."""

    @extend_schema(
        operation_id="profile_retrieve",
        responses={200: DeveloperProfileSerializer, **error_responses(401, 404)},
    )
    def get(self, request: Request) -> Response:
        profile = (
            DeveloperProfile.objects.filter(user=current_user(request))
            .annotate(
                skill_count=Count("skills", distinct=True),
                interest_count=Count("interests", distinct=True),
            )
            .first()
        )
        if profile is None:
            raise NotAnalyzed()
        return Response(DeveloperProfileSerializer(profile).data)


class ProfileListPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


# django-filter ships no type information.
class SkillFilter(filters.FilterSet):  # type: ignore[misc]
    category = filters.ChoiceFilter(field_name="skill__category", choices=SkillCategory.choices)

    class Meta:
        model = DeveloperSkill
        fields = ["category"]


class SkillListView(ListAPIView[DeveloperSkill]):
    """Detected skills with their evidence, highest confidence first."""

    serializer_class = DeveloperSkillSerializer
    pagination_class = ProfileListPagination
    filterset_class = SkillFilter

    def get_queryset(self) -> QuerySet[DeveloperSkill]:
        if getattr(self, "swagger_fake_view", False):  # schema generation: no request user
            return DeveloperSkill.objects.none()
        evidence = SkillEvidence.objects.select_related("repository").order_by(
            "source", "-observed_at", "pk"
        )
        return (
            DeveloperSkill.objects.filter(profile__user=current_user(self.request))
            .select_related("skill")
            .prefetch_related(Prefetch("evidence", queryset=evidence))
            .order_by("-confidence", "skill__name")
        )

    @extend_schema(
        operation_id="profile_skills",
        responses={200: DeveloperSkillSerializer(many=True), **error_responses(401)},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)


class InterestListView(ListAPIView[DeveloperInterest]):
    """Detected interests with their evidence, strongest first."""

    serializer_class = DeveloperInterestSerializer
    pagination_class = ProfileListPagination
    filter_backends = []

    def get_queryset(self) -> QuerySet[DeveloperInterest]:
        evidence = InterestEvidence.objects.select_related("repository").order_by(
            "source", "-observed_at", "pk"
        )
        return (
            DeveloperInterest.objects.filter(profile__user=current_user(self.request))
            .select_related("interest")
            .prefetch_related(Prefetch("evidence", queryset=evidence))
            .order_by("-strength", "interest__name")
        )

    @extend_schema(
        operation_id="profile_interests",
        responses={200: DeveloperInterestSerializer(many=True), **error_responses(401)},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)
