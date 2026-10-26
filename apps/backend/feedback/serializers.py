"""Feedback, saved and dismissed API shapes (spec: recommendation-feedback)."""

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from recommendations.models import MatchLabel, Recommendation
from recommendations.serializers import ReasonSerializer
from repositories.models import ActivityLabel
from repositories.serializers import CandidateRepositorySerializer
from services.feedback import CLIENT_ACTIONS

from .models import DismissedRepository, DismissReason, FeedbackAction, SavedRepository


class FeedbackSerializer(serializers.Serializer[dict[str, Any]]):
    action = serializers.ChoiceField(
        choices=[str(action) for action in CLIENT_ACTIONS],
        help_text="Saves and dismissals are recorded by their own endpoints.",
    )
    issue_id = serializers.IntegerField(
        required=False,
        help_text="Required for opened_issue: one of the recommendation's relevant issues.",
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        opened_issue = attrs["action"] == FeedbackAction.OPENED_ISSUE
        if opened_issue and attrs.get("issue_id") is None:
            raise serializers.ValidationError({"issue_id": "Required for opened_issue."})
        if not opened_issue and "issue_id" in attrs:
            raise serializers.ValidationError({"issue_id": "Only allowed for opened_issue."})
        return attrs


class DismissSerializer(serializers.Serializer[dict[str, Any]]):
    reason = serializers.ChoiceField(
        choices=DismissReason.choices,
        required=False,
        help_text="Optional: why the project is not for the user. Never used for ranking.",
    )


class SaveResultSerializer(serializers.Serializer[dict[str, bool]]):
    saved = serializers.BooleanField()


class SavedRecommendationSerializer(serializers.ModelSerializer[Recommendation]):
    match_label = serializers.ChoiceField(choices=MatchLabel.choices, read_only=True)
    reasons = ReasonSerializer(many=True, read_only=True)

    class Meta:
        model = Recommendation
        fields = ["id", "match_label", "reasons"]
        read_only_fields = fields


class SavedRepositorySerializer(serializers.ModelSerializer[SavedRepository]):
    repository_id = serializers.IntegerField(read_only=True)
    repository = CandidateRepositorySerializer(read_only=True)
    activity_label = serializers.SerializerMethodField(
        help_text="Current activity label; empty when unknown."
    )
    recommendation = serializers.SerializerMethodField(
        help_text="The current recommendation, or null when it is no longer recommended."
    )

    class Meta:
        model = SavedRepository
        fields = ["repository_id", "repository", "saved_at", "activity_label", "recommendation"]
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=ActivityLabel.choices, allow_blank=True))
    def get_activity_label(self, obj: SavedRepository) -> str:
        snapshots = obj.repository.latest_snapshots  # type: ignore[attr-defined]
        return str(snapshots[0].activity_label) if snapshots else ""

    @extend_schema_field(SavedRecommendationSerializer(allow_null=True))
    def get_recommendation(self, obj: SavedRepository) -> dict[str, Any] | None:
        recs = obj.repository.user_recommendations  # type: ignore[attr-defined]
        return SavedRecommendationSerializer(recs[0]).data if recs else None


class DismissedRepositorySerializer(serializers.ModelSerializer[DismissedRepository]):
    repository_id = serializers.IntegerField(read_only=True)
    repository = CandidateRepositorySerializer(read_only=True)
    reason = serializers.SerializerMethodField(help_text="The reason given, or null when none.")

    class Meta:
        model = DismissedRepository
        fields = ["repository_id", "repository", "dismissed_at", "reason"]
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=DismissReason.choices, allow_null=True))
    def get_reason(self, obj: DismissedRepository) -> str | None:
        return obj.reason or None
