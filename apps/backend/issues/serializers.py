"""Issue detail shapes (spec: issue-matching). GitHub data and ContribFinder analysis are
separate objects; the internal issue score is never included."""

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from recommendations.models import MatchLabel
from recommendations.serializers import IssueReasonSerializer
from services.issues import technologies
from services.profiling.taxonomy import SKILLS_BY_SLUG

from .models import ContributionType, Difficulty, DifficultySignal, RecommendedIssue


class IssueGitHubSerializer(serializers.Serializer[RecommendedIssue]):
    """As GitHub sent it. ``body`` is plain text: render it escaped, never as HTML."""

    repository_full_name = serializers.CharField(source="issue.repository.full_name")
    number = serializers.IntegerField(source="issue.number")
    title = serializers.CharField(source="issue.title")
    body = serializers.CharField(source="issue.body")
    labels = serializers.ListField(child=serializers.CharField(), source="issue.raw_labels")
    state = serializers.CharField(source="issue.state")
    comments = serializers.IntegerField(source="issue.comments")
    created_at = serializers.DateTimeField(source="issue.github_created_at", allow_null=True)
    updated_at = serializers.DateTimeField(source="issue.github_updated_at", allow_null=True)
    url = serializers.URLField(source="issue.html_url")


class IssueTechnologySerializer(serializers.Serializer[dict[str, Any]]):
    slug = serializers.CharField()
    name = serializers.CharField()
    # A field named like Field.source: DRF moves it into the declared fields at class creation.
    source = serializers.ChoiceField(  # type: ignore[assignment]
        choices=[technologies.TITLE, technologies.LABEL, technologies.BODY]
    )
    matched = serializers.BooleanField(help_text="The developer has demonstrated it.")


class IssueRecommendationSerializer(serializers.Serializer[RecommendedIssue]):
    id = serializers.IntegerField(source="recommendation.id")
    repository_full_name = serializers.CharField(source="recommendation.repository.full_name")
    match_label = serializers.ChoiceField(
        choices=MatchLabel.choices, source="recommendation.match_label"
    )


class DifficultyVoteSerializer(serializers.Serializer[dict[str, Any]]):
    signal = serializers.ChoiceField(choices=DifficultySignal.choices)
    vote = serializers.ChoiceField(
        choices=Difficulty.choices, allow_null=True, help_text="The level it voted for, if any."
    )
    value = serializers.JSONField(help_text="What the signal measured (label, length, count).")


class DifficultyEvidenceSerializer(serializers.Serializer[dict[str, Any]]):
    """How the difficulty estimate was reached. Returned as stored: an older issue may lack
    keys or name a signal not listed here."""

    signals = DifficultyVoteSerializer(many=True, required=False)
    votes = serializers.DictField(child=serializers.IntegerField(), required=False)
    thresholds = serializers.DictField(child=serializers.IntegerField(), required=False)


@extend_schema_field(DifficultyEvidenceSerializer)
class DifficultyEvidenceField(serializers.DictField):
    """``difficulty_evidence`` passed through unchanged, described by
    ``DifficultyEvidenceSerializer`` in the schema."""


class IssueAnalysisSerializer(serializers.Serializer[RecommendedIssue]):
    labels = serializers.ListField(
        child=serializers.CharField(),
        source="issue.labels",
        help_text="Canonical label categories.",
    )
    contribution_type = serializers.ChoiceField(
        choices=ContributionType.choices, source="issue.contribution_type"
    )
    contribution_type_evidence = serializers.DictField(source="issue.contribution_type_evidence")
    difficulty = serializers.ChoiceField(
        choices=Difficulty.choices,
        source="issue.difficulty",
        help_text="Estimated; unknown when the evidence is not enough.",
    )
    difficulty_evidence = DifficultyEvidenceField(source="issue.difficulty_evidence")
    technologies = serializers.SerializerMethodField()
    reasons = IssueReasonSerializer(many=True)
    recommendation = IssueRecommendationSerializer(source="*")

    @extend_schema_field(IssueTechnologySerializer(many=True))
    def get_technologies(self, obj: RecommendedIssue) -> list[dict[str, Any]]:
        known: set[str] = self.context.get("developer_skills", set())
        result = []
        for tech in obj.issue.technologies:
            skill = SKILLS_BY_SLUG.get(tech["slug"])
            result.append(
                {
                    "slug": tech["slug"],
                    "name": skill.name if skill else tech["slug"],
                    "source": tech["source"],
                    "matched": tech["slug"] in known,
                }
            )
        return result


class IssueDetailSerializer(serializers.Serializer[RecommendedIssue]):
    id = serializers.IntegerField(source="issue.id")
    github = IssueGitHubSerializer(source="*")
    analysis = IssueAnalysisSerializer(source="*")
