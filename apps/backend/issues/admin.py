from django.contrib import admin

from core.admin import ViewOnlyAdmin

from .models import Issue, RecommendedIssue


@admin.register(Issue)
class IssueAdmin(ViewOnlyAdmin[Issue]):
    list_display = (
        "repository",
        "number",
        "title",
        "contribution_type",
        "difficulty",
        "github_updated_at",
    )
    list_filter = ("contribution_type", "difficulty", "has_assignee", "is_locked")
    list_select_related = ("repository",)
    search_fields = ("repository__full_name", "title")


@admin.register(RecommendedIssue)
class RecommendedIssueAdmin(ViewOnlyAdmin[RecommendedIssue]):
    # Recommendation.__str__ and Issue.__str__ read only ids: no related rows to select.
    list_display = ("recommendation", "rank", "issue", "score")
