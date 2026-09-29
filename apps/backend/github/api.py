from django.db.models import F, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses
from repositories.models import Repository, UserRepository

from .models import GitHubProfile
from .serializers import GitHubProfileSerializer, RepositorySerializer


class NotSynced(NotFound):
    default_code = "not_synced"
    default_detail = "Your GitHub data has not been synced yet."


class GitHubProfileView(APIView):
    """Stored data only: never calls GitHub."""

    @extend_schema(
        operation_id="profile_github",
        responses={200: GitHubProfileSerializer, **error_responses(401, 404)},
    )
    def get(self, request: Request) -> Response:
        profile = GitHubProfile.objects.filter(user=current_user(request)).first()
        if profile is None:
            raise NotSynced()
        return Response(GitHubProfileSerializer(profile).data)


class RepositoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    # Matches the default per-sync repository cap, so one request can return every repo.
    max_page_size = 100


class RepositoryListView(ListAPIView[Repository]):
    """Repositories the user owns, most recently pushed first. Stored data only. Repositories
    they only contributed to are profile evidence and are not listed here."""

    serializer_class = RepositorySerializer
    pagination_class = RepositoryPagination
    filter_backends = []

    def get_queryset(self) -> QuerySet[Repository]:
        return (
            Repository.objects.filter(
                user_links__user=current_user(self.request),
                user_links__relation=UserRepository.Relation.OWNER,
            )
            .prefetch_related("languages", "topics")
            .order_by(F("pushed_at").desc(nulls_last=True), "full_name")
            .distinct()
        )

    @extend_schema(
        operation_id="profile_repositories",
        responses={200: RepositorySerializer(many=True), **error_responses(401)},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)
