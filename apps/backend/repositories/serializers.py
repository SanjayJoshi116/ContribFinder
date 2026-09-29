from typing import Any

from rest_framework import serializers

from jobs.serializers import SyncJobSerializer

from .models import (
    ActivityLabel,
    CandidateDiscovery,
    Lifecycle,
    Repository,
    RepositoryCandidate,
)


class CandidateRepositorySerializer(serializers.ModelSerializer[Repository]):
    owner = serializers.CharField(source="owner_login")
    license = serializers.CharField(source="license_spdx")
    topics = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = [
            "full_name",
            "owner",
            "name",
            "description",
            "html_url",
            "primary_language",
            "stars",
            "topics",
            "license",
        ]
        read_only_fields = fields

    def get_topics(self, obj: Repository) -> list[str]:
        return [t.topic for t in obj.topics.all()]


class CandidateDiscoverySerializer(serializers.ModelSerializer[CandidateDiscovery]):
    class Meta:
        model = CandidateDiscovery
        fields = ["source", "query", "search_rank", "first_seen_at", "last_seen_at"]
        read_only_fields = fields


class RepositoryCandidateSerializer(serializers.ModelSerializer[RepositoryCandidate]):
    """A candidate in the developer's pool and why it is there. Deliberately carries no score
    or rank across candidates: relevance is Phase 5's job."""

    repository = CandidateRepositorySerializer(read_only=True)
    lifecycle = serializers.ChoiceField(
        source="repository.lifecycle", choices=Lifecycle.choices, read_only=True
    )
    eligible = serializers.BooleanField(
        source="repository.is_eligible", allow_null=True, read_only=True
    )
    ineligible_reason = serializers.CharField(source="repository.ineligible_reason")
    activity_label = serializers.ChoiceField(
        choices=ActivityLabel.choices, allow_null=True, read_only=True
    )
    discoveries = CandidateDiscoverySerializer(many=True, read_only=True)

    class Meta:
        model = RepositoryCandidate
        fields = [
            "id",
            "repository",
            "lifecycle",
            "eligible",
            "ineligible_reason",
            "activity_label",
            "discoveries",
            "first_discovered_at",
            "last_seen_at",
        ]
        read_only_fields = fields


class PoolCountsSerializer(serializers.Serializer[dict[str, Any]]):
    total = serializers.IntegerField()
    eligible = serializers.IntegerField()
    awaiting_analysis = serializers.IntegerField()
    ineligible = serializers.IntegerField()
    by_source = serializers.DictField(child=serializers.IntegerField())


class DiscoveryStatusSerializer(serializers.Serializer[dict[str, Any]]):
    job = SyncJobSerializer(allow_null=True)
    last_completed_at = serializers.DateTimeField(allow_null=True)
    pool = PoolCountsSerializer()
