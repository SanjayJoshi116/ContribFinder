"""Feedback, save and dismiss endpoints (spec: recommendation-feedback; design D4). Thin
wrappers around ``services.feedback``."""

import base64
import binascii
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from django.db.models import Model, Prefetch, Q, QuerySet
from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param
from rest_framework.views import APIView

from core.authentication import current_user
from core.serializers import error_responses
from recommendations.models import Recommendation
from repositories.queries import latest_snapshot
from services import feedback

from .models import DismissedRepository, SavedRepository
from .serializers import (
    DismissedRepositorySerializer,
    DismissSerializer,
    FeedbackSerializer,
    SavedRepositorySerializer,
    SaveResultSerializer,
)

_NO_CONTENT = OpenApiResponse(description="Done.")


def _own_recommendation(request: Request, pk: int) -> Recommendation:
    """The requesting user's recommendation, pk and repository id only; 404 for anyone
    else's. The services re-read the row under their locks (FB-5)."""
    return get_object_or_404(
        Recommendation.objects.only("pk", "repository_id"),
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
        try:
            feedback.record(
                current_user(request),
                recommendation,
                body.validated_data["action"],
                issue_id=body.validated_data.get("issue_id"),
            )
        except feedback.IssueNotRelevant:
            raise ValidationError(
                {"issue_id": "Not a relevant issue of this recommendation."}
            ) from None
        return Response(status=204)


class SaveView(APIView):
    @extend_schema(
        operation_id="recommendations_save",
        request=None,
        responses={200: SaveResultSerializer, **error_responses(401, 403, 404)},
    )
    def post(self, request: Request, pk: int) -> Response:
        try:
            feedback.save(current_user(request), _own_recommendation(request, pk))
        except Recommendation.DoesNotExist:
            raise Http404 from None  # dismissed (or regenerated away) meanwhile
        return Response(SaveResultSerializer({"saved": True}).data)

    @extend_schema(
        operation_id="recommendations_unsave",
        responses={200: SaveResultSerializer, **error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, pk: int) -> Response:
        # Kept for API clients (OpenAPI 1.0.0); the SPA unsaves through DELETE /saved/{id},
        # which still works once the recommendation is regenerated away (FB-3).
        recommendation = _own_recommendation(request, pk)
        feedback.unsave(current_user(request), recommendation.repository_id)
        return Response(SaveResultSerializer({"saved": False}).data)


class DismissView(APIView):
    @extend_schema(
        operation_id="recommendations_dismiss",
        request=DismissSerializer,
        responses={204: _NO_CONTENT, **error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, pk: int) -> Response:
        recommendation = _own_recommendation(request, pk)
        body = DismissSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            feedback.dismiss(
                current_user(request), recommendation, body.validated_data.get("reason", "")
            )
        except Recommendation.DoesNotExist:
            raise Http404 from None  # its repository was deleted with the user's data meanwhile
        return Response(status=204)


class InvalidCursor(APIException):
    status_code = 400
    default_code = "invalid_cursor"
    default_detail = "The page cursor is not valid."


class CursorWithPage(APIException):
    status_code = 400
    default_code = "cursor_with_page"
    default_detail = "Send either a cursor or a page number, not both."


class KeysetPagination(PageNumberPagination):
    """Pages newest first by (``time_field``, pk), continuing after the previous page's last
    entry (spec recommendation-feedback, "Complete saved and hidden lists"; design D2), so
    entries added or removed between requests never shift a page. ``next`` carries an opaque
    ``cursor``; without one, ``page`` works as before, and a request with both is refused.
    Lists page forward only: ``previous`` is always null, so every link is a cursor link.
    ``count`` is always the total. The paginator applies the order itself, since the keyset
    filter depends on it."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    cursor_query_param = "cursor"
    time_field = ""
    total = 0
    next_link: str | None = None

    def paginate_queryset(
        self,
        queryset: QuerySet[Any, Any] | Sequence[Any],
        request: Request,
        view: APIView | None = None,
    ) -> list[Any] | None:
        if not isinstance(queryset, QuerySet):
            raise TypeError("KeysetPagination pages a QuerySet")
        queryset = queryset.order_by(f"-{self.time_field}", "-pk")
        self.base_url = remove_query_param(request.build_absolute_uri(), self.page_query_param)
        raw = request.query_params.get(self.cursor_query_param)
        if raw is not None and self.page_query_param in request.query_params:
            raise CursorWithPage
        if raw is None:
            rows = super().paginate_queryset(queryset, request, view) or []
            self.total = self.page.paginator.count if self.page is not None else 0
            has_more = self.page is not None and self.page.has_next()
        else:
            time, pk = self.decode(raw)
            self.total = queryset.count()
            size = self.get_page_size(request) or self.page_size
            after = Q(**{f"{self.time_field}__lt": time}) | Q(**{self.time_field: time}, pk__lt=pk)
            rows = list(queryset.filter(after)[: size + 1])
            has_more = len(rows) > size
            rows = rows[:size]
        self.next_link = self._next(rows[-1]) if has_more else None
        return rows

    def get_paginated_response(self, data: Any) -> Response:
        return Response(
            {"count": self.total, "next": self.next_link, "previous": None, "results": data}
        )

    def _next(self, last: Model) -> str:
        return replace_query_param(self.base_url, self.cursor_query_param, self.encode(last))

    def encode(self, row: Model) -> str:
        value = f"{getattr(row, self.time_field).isoformat()}|{row.pk}"
        return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")

    @staticmethod
    def decode(raw: str) -> tuple[datetime, int]:
        try:
            value = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
            time, pk = value.split("|")
            parsed = datetime.fromisoformat(time)
            if parsed.tzinfo is None:
                raise ValueError("naive time")
            return parsed, int(pk)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            raise InvalidCursor from None

    def get_schema_operation_parameters(self, view: APIView) -> list[dict[str, Any]]:
        return [
            *super().get_schema_operation_parameters(view),
            {
                "name": self.cursor_query_param,
                "required": False,
                "in": "query",
                "description": "Continue after the entry this opaque value marks (from `next`). "
                "Cannot be combined with `page`.",
                "schema": {"type": "string"},
            },
        ]


class SavedPagination(KeysetPagination):
    time_field = "saved_at"


class DismissedPagination(KeysetPagination):
    time_field = "dismissed_at"


class SavedListView(ListAPIView[SavedRepository]):
    """Saved repositories, most recently saved first, whether or not still recommended."""

    serializer_class = SavedRepositorySerializer
    pagination_class = SavedPagination
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
                latest_snapshot("repository__"),
                Prefetch(
                    "repository__recommendations",
                    queryset=Recommendation.objects.filter(developer__user=user).prefetch_related(
                        "reasons"
                    ),
                    to_attr="user_recommendations",
                ),
            )
        )  # SavedPagination orders

    @extend_schema(
        operation_id="saved_list",
        responses={200: SavedRepositorySerializer(many=True), **error_responses(400, 401)},
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
    pagination_class = DismissedPagination
    filter_backends = []

    def get_queryset(self) -> QuerySet[DismissedRepository]:
        if getattr(self, "swagger_fake_view", False):
            return DismissedRepository.objects.none()
        return (
            DismissedRepository.objects.filter(user=current_user(self.request))
            .select_related("repository")
            .prefetch_related("repository__topics")
        )  # DismissedPagination orders

    @extend_schema(
        operation_id="dismissed_list",
        responses={200: DismissedRepositorySerializer(many=True), **error_responses(400, 401)},
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
