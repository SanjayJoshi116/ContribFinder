from django.contrib import admin

from recommendations.admin import ReadOnlyAdmin

from .models import DismissedRepository, RecommendationFeedback, SavedRepository


@admin.register(RecommendationFeedback)
class RecommendationFeedbackAdmin(ReadOnlyAdmin[RecommendationFeedback]):
    list_display = ("created_at", "user", "action", "repository_full_name", "match_label", "rank")
    list_filter = ("action", "match_label")
    search_fields = ("repository_full_name",)


@admin.register(SavedRepository)
class SavedRepositoryAdmin(ReadOnlyAdmin[SavedRepository]):
    list_display = ("saved_at", "user", "repository")


@admin.register(DismissedRepository)
class DismissedRepositoryAdmin(ReadOnlyAdmin[DismissedRepository]):
    list_display = ("dismissed_at", "user", "repository")
