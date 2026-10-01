"""Feedback, saved and dismissed API shapes (spec: recommendation-feedback)."""

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from recommendations.models import MatchLabel, Recommendation
from recommendations.serializers import ReasonSerializer
from repositories.models import ActivityLabel
from repositories.serializers import CandidateRepositorySerializer
from services.feedback import CLIENT_ACTIONS

from .models import DismissedRepository, SavedRepository


class FeedbackSerializer(serializers.Serializer[dict[str, str]]):
    action = serializers.ChoiceField(
        choices=[str(action) for action in CLIENT_ACTIONS],
        help_text="Saves and dismissals are recorded by their own endpoints.",
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
        snapshots = obj.repository.ordered_snapshots  # type: ignore[attr-defined]
        return str(snapshots[0].activity_label) if snapshots else ""

    @extend_schema_field(SavedRecommendationSerializer(allow_null=True))
    def get_recommendation(self, obj: SavedRepository) -> dict[str, Any] | None:
        recs = obj.repository.user_recommendations  # type: ignore[attr-defined]
        return SavedRecommendationSerializer(recs[0]).data if recs else None


class DismissedRepositorySerializer(serializers.ModelSerializer[DismissedRepository]):
    repository_id = serializers.IntegerField(read_only=True)
    repository = CandidateRepositorySerializer(read_only=True)

    class Meta:
        model = DismissedRepository
        fields = ["repository_id", "repository", "dismissed_at"]
        read_only_fields = fields
