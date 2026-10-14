from django.contrib import admin

from recommendations.admin import ReadOnlyAdmin

from .models import Issue, RecommendedIssue


@admin.register(Issue)
class IssueAdmin(ReadOnlyAdmin[Issue]):
    list_display = (
        "repository",
        "number",
        "title",
        "contribution_type",
        "difficulty",
        "github_updated_at",
    )
    list_filter = ("contribution_type", "difficulty", "has_assignee", "is_locked")
    search_fields = ("repository__full_name", "title")
    readonly_fields = (
        "raw_labels",
        "labels",
        "contribution_type_evidence",
        "difficulty_evidence",
        "technologies",
    )


@admin.register(RecommendedIssue)
class RecommendedIssueAdmin(ReadOnlyAdmin[RecommendedIssue]):
    list_display = ("recommendation", "rank", "issue", "score")
    readonly_fields = ("reasons",)
