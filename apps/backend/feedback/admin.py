from django.contrib import admin

from core.admin import ViewOnlyAdmin

from .models import DismissedRepository, RecommendationFeedback, SavedRepository


@admin.register(RecommendationFeedback)
class RecommendationFeedbackAdmin(ViewOnlyAdmin[RecommendationFeedback]):
    list_display = ("created_at", "user", "action", "repository_full_name", "match_label", "rank")
    list_filter = ("action", "match_label")
    list_select_related = ("user",)
    search_fields = ("repository_full_name",)


@admin.register(SavedRepository)
class SavedRepositoryAdmin(ViewOnlyAdmin[SavedRepository]):
    list_display = ("saved_at", "user", "repository")
    list_select_related = ("user", "repository")


@admin.register(DismissedRepository)
class DismissedRepositoryAdmin(ViewOnlyAdmin[DismissedRepository]):
    # Deleting a dismissal outside services.feedback.restore would bring the project back with
    # no ``undismissed`` event and no generation.
    list_display = ("dismissed_at", "user", "repository")
    list_select_related = ("user", "repository")
