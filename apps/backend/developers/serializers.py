from collections import Counter
from typing import Any

from rest_framework import serializers

from repositories.models import Repository

from .models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    Interest,
    InterestEvidence,
    Skill,
    SkillEvidence,
    SkillSource,
)


class ProfileLanguageSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField()
    bytes = serializers.IntegerField()
    share = serializers.FloatField()
    repo_count = serializers.IntegerField()


class DeveloperProfileSerializer(serializers.ModelSerializer[DeveloperProfile]):
    """The analyzed profile. The experience level is an internal matching signal and is
    deliberately not part of this representation (SRS-2 §17)."""

    languages = ProfileLanguageSerializer(many=True, read_only=True)
    skill_count = serializers.IntegerField(read_only=True)
    interest_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DeveloperProfile
        fields = [
            "summary",
            "languages",
            "preferred_project_size",
            "preferred_issue_difficulty",
            "analyzed_at",
            "skill_count",
            "interest_count",
        ]
        read_only_fields = fields


class EvidenceRepositorySerializer(serializers.ModelSerializer[Repository]):
    class Meta:
        model = Repository
        fields = ["full_name", "html_url"]
        read_only_fields = fields


class SkillEvidenceSerializer(serializers.ModelSerializer[SkillEvidence]):
    repository = EvidenceRepositorySerializer(read_only=True, allow_null=True)

    class Meta:
        model = SkillEvidence
        fields = ["source", "repository", "detail", "observed_at"]
        read_only_fields = fields


class EvidenceSummarySerializer(serializers.Serializer[DeveloperSkill]):
    """Counts computed from the (prefetched) evidence of one skill."""

    by_source = serializers.DictField(child=serializers.IntegerField())
    repository_count = serializers.IntegerField()
    last_observed_at = serializers.DateTimeField(allow_null=True)

    def to_representation(self, instance: DeveloperSkill) -> dict[str, Any]:
        evidence = list(instance.evidence.all())
        counts = Counter(e.source for e in evidence)
        return {
            "by_source": {s: counts[s] for s in SkillSource.values if counts[s]},
            "repository_count": len({e.repository_id for e in evidence if e.repository_id}),
            "last_observed_at": serializers.DateTimeField().to_representation(
                instance.last_observed_at
            )
            if instance.last_observed_at
            else None,
        }


class SkillSerializer(serializers.ModelSerializer[Skill]):
    class Meta:
        model = Skill
        fields = ["slug", "name", "category"]
        read_only_fields = fields


class DeveloperSkillSerializer(serializers.ModelSerializer[DeveloperSkill]):
    """``confidence`` (0-1) drives ranking and bar width; the UI never prints it."""

    skill = SkillSerializer(read_only=True)
    evidence_summary = EvidenceSummarySerializer(source="*", read_only=True)
    evidence = SkillEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = DeveloperSkill
        fields = ["id", "skill", "confidence", "evidence_summary", "evidence"]
        read_only_fields = fields


class InterestSerializer(serializers.ModelSerializer[Interest]):
    class Meta:
        model = Interest
        fields = ["slug", "name"]
        read_only_fields = fields


class InterestEvidenceSerializer(serializers.ModelSerializer[InterestEvidence]):
    repository = EvidenceRepositorySerializer(read_only=True, allow_null=True)

    class Meta:
        model = InterestEvidence
        fields = ["source", "repository", "detail", "observed_at"]
        read_only_fields = fields


class DeveloperInterestSerializer(serializers.ModelSerializer[DeveloperInterest]):
    interest = InterestSerializer(read_only=True)
    evidence = InterestEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = DeveloperInterest
        fields = ["id", "interest", "strength", "evidence"]
        read_only_fields = fields
