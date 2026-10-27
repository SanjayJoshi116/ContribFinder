"""Recommendation API shapes (spec: recommendations-view). The numeric score, rank and signal
values are internal ranking data and deliberately absent: users see the match label and the
reasons behind it."""

import re
from typing import Any

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from issues.models import ContributionType, Difficulty, RecommendedIssue
from jobs.serializers import SyncJobSerializer
from repositories.models import ActivityLabel, Repository, RepositorySnapshot
from repositories.serializers import CandidateRepositorySerializer
from services.profiling.text import plain_text

from .models import MatchLabel, Recommendation, RecommendationReason, RepositorySize

_MARKDOWN_NOISE = re.compile(r"[#*_>`|~]+|!\[[^\]]*\]|\[|\]")
_WHITESPACE = re.compile(r"\s+")


def readme_excerpt(content: str, limit: int) -> str:
    """Plain-text start of a README, cut at a word boundary."""
    text = _WHITESPACE.sub(" ", _MARKDOWN_NOISE.sub(" ", plain_text(content))).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{cut}…"


class TechnologySerializer(serializers.Serializer[dict[str, Any]]):
    slug = serializers.CharField()
    name = serializers.CharField()
    category = serializers.CharField()
    matched = serializers.BooleanField()


class ReasonSerializer(serializers.ModelSerializer[RecommendationReason]):
    class Meta:
        model = RecommendationReason
        fields = ["type", "text", "detail"]
        read_only_fields = fields


class IssueReasonSerializer(serializers.Serializer[dict[str, Any]]):
    type = serializers.ChoiceField(choices=["technology", "difficulty", "approachability"])
    text = serializers.CharField()
    detail = serializers.DictField()


class RelevantIssueSerializer(serializers.ModelSerializer[RecommendedIssue]):
    """A relevant issue of a recommendation, without its internal score."""

    id = serializers.IntegerField(source="issue.id", read_only=True)
    number = serializers.IntegerField(source="issue.number", read_only=True)
    title = serializers.CharField(source="issue.title", read_only=True)
    url = serializers.URLField(source="issue.html_url", read_only=True)
    labels = serializers.ListField(
        child=serializers.CharField(),
        source="issue.labels",
        read_only=True,
        help_text="Canonical label categories (ContribFinder analysis).",
    )
    contribution_type = serializers.ChoiceField(
        choices=ContributionType.choices, source="issue.contribution_type", read_only=True
    )
    difficulty = serializers.ChoiceField(
        choices=Difficulty.choices,
        source="issue.difficulty",
        read_only=True,
        help_text="Estimated; unknown when the evidence is not enough.",
    )
    reasons = IssueReasonSerializer(many=True, read_only=True)

    class Meta:
        model = RecommendedIssue
        fields = [
            "id",
            "number",
            "title",
            "url",
            "labels",
            "contribution_type",
            "difficulty",
            "reasons",
        ]
        read_only_fields = fields


class OpennessSerializer(serializers.ModelSerializer[Repository]):
    """Observable contribution affordances; null means not yet known."""

    contributing = serializers.BooleanField(source="has_contributing", allow_null=True)
    code_of_conduct = serializers.BooleanField(source="has_code_of_conduct", allow_null=True)
    issue_templates = serializers.BooleanField(source="has_issue_templates", allow_null=True)
    pull_request_template = serializers.BooleanField(
        source="has_pull_request_template", allow_null=True
    )
    good_first_issue = serializers.BooleanField(
        source="has_good_first_issue_label", allow_null=True
    )
    help_wanted = serializers.BooleanField(source="has_help_wanted_label", allow_null=True)

    class Meta:
        model = Repository
        fields = [
            "contributing",
            "code_of_conduct",
            "issue_templates",
            "pull_request_template",
            "good_first_issue",
            "help_wanted",
        ]
        read_only_fields = fields


class SetupSerializer(serializers.ModelSerializer[Repository]):
    """Setup facts seen at the repository root: true found, false not found there, null not
    yet known. Shown only, never scored."""

    ci = serializers.BooleanField(source="has_ci", allow_null=True)
    tests = serializers.BooleanField(source="has_tests", allow_null=True)
    dev_environment = serializers.BooleanField(source="has_dev_environment", allow_null=True)
    docker_compose = serializers.BooleanField(source="has_docker_compose", allow_null=True)

    class Meta:
        model = Repository
        fields = ["ci", "tests", "dev_environment", "docker_compose"]
        read_only_fields = fields


class RecommendationSerializer(serializers.ModelSerializer[Recommendation]):
    repository_id = serializers.IntegerField(
        read_only=True, help_text="For the saved and dismissed endpoints."
    )
    repository = CandidateRepositorySerializer(read_only=True)
    match_label = serializers.ChoiceField(choices=MatchLabel.choices, read_only=True)
    technologies = TechnologySerializer(many=True, read_only=True)
    reasons = ReasonSerializer(many=True, read_only=True)
    activity_label = serializers.ChoiceField(
        choices=ActivityLabel.choices,
        allow_blank=True,
        read_only=True,
        help_text="Empty when the repository's activity is unknown.",
    )
    size = serializers.ChoiceField(choices=RepositorySize.choices, read_only=True)
    openness = OpennessSerializer(source="repository", read_only=True)
    setup = SetupSerializer(source="repository", read_only=True)
    saved = serializers.BooleanField(read_only=True, help_text="Whether the user saved it.")
    relevant_issue_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Recommendation
        fields = [
            "id",
            "repository_id",
            "repository",
            "match_label",
            "technologies",
            "reasons",
            "activity_label",
            "size",
            "openness",
            "setup",
            "saved",
            "relevant_issue_count",
            "generated_at",
        ]
        read_only_fields = fields


class LanguageShareSerializer(serializers.Serializer[dict[str, Any]]):
    language = serializers.CharField()
    share = serializers.FloatField(help_text="Fraction of the repository's code, 0..1.")


class ActivitySignalsSerializer(serializers.ModelSerializer[RepositorySnapshot]):
    class Meta:
        model = RepositorySnapshot
        fields = [
            "captured_at",
            "days_since_push",
            "commits_90d",
            "prs_merged_90d",
            "contributors",
            "latest_release_at",
            "open_issues",
        ]
        read_only_fields = fields


class RecommendationDetailSerializer(RecommendationSerializer):
    languages = serializers.SerializerMethodField()
    readme_excerpt = serializers.SerializerMethodField()
    activity_signals = serializers.SerializerMethodField()
    issues = RelevantIssueSerializer(
        source="recommended_issues", many=True, read_only=True, help_text="Best first."
    )

    class Meta(RecommendationSerializer.Meta):
        fields = [
            *RecommendationSerializer.Meta.fields,
            "languages",
            "readme_excerpt",
            "activity_signals",
            "issues",
        ]
        read_only_fields = fields

    @extend_schema_field(LanguageShareSerializer(many=True))
    def get_languages(self, obj: Recommendation) -> list[dict[str, Any]]:
        languages = sorted(obj.repository.languages.all(), key=lambda lang: -lang.bytes)
        total = sum(lang.bytes for lang in languages) or 1
        return [
            {"language": lang.language, "share": round(lang.bytes / total, 4)} for lang in languages
        ]

    def get_readme_excerpt(self, obj: Recommendation) -> str:
        readme = getattr(obj.repository, "readme", None)
        if readme is None:
            return ""
        return readme_excerpt(readme.content, settings.RECOMMENDATION_README_EXCERPT_CHARS)

    @extend_schema_field(ActivitySignalsSerializer(allow_null=True))
    def get_activity_signals(self, obj: Recommendation) -> dict[str, Any] | None:
        snapshots = obj.repository.latest_snapshots  # type: ignore[attr-defined]
        return ActivitySignalsSerializer(snapshots[0]).data if snapshots else None


class RecommendationStatusSerializer(serializers.Serializer[dict[str, Any]]):
    job = SyncJobSerializer(allow_null=True)
    last_generated_at = serializers.DateTimeField(allow_null=True)
    count = serializers.IntegerField()
    config_version = serializers.CharField(allow_null=True)
