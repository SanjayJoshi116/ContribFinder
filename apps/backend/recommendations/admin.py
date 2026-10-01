from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import HttpRequest

from .models import Recommendation, RecommendationReason, ScoringConfig


class ReadOnlyAdmin[M: Model](admin.ModelAdmin[M]):
    """Recommendations are rebuilt by background jobs; editing them here would be overwritten."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return False


@admin.register(ScoringConfig)
class ScoringConfigAdmin(admin.ModelAdmin[ScoringConfig]):
    list_display = ("version", "is_active", "created_at")
    readonly_fields = ("is_active", "created_at")
    actions = ["activate"]

    def get_readonly_fields(
        self, request: HttpRequest, obj: ScoringConfig | None = None
    ) -> list[str] | tuple[str, ...]:
        # A version that produced recommendations must keep meaning the same numbers.
        if obj is not None and obj.recommendations.exists():
            return (*self.readonly_fields, "version", "weights", "params")
        return self.readonly_fields

    @admin.action(description="Activate the selected configuration")
    def activate(self, request: HttpRequest, queryset: QuerySet[ScoringConfig]) -> None:
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one configuration.", messages.ERROR)
            return
        config = queryset.get()
        with transaction.atomic():
            ScoringConfig.objects.exclude(pk=config.pk).update(is_active=False)
            ScoringConfig.objects.filter(pk=config.pk).update(is_active=True)
        self.message_user(
            request, f"{config.version} is active; recommendations regenerate on the next refresh."
        )


class ReasonInline(admin.TabularInline[RecommendationReason, Recommendation]):
    model = RecommendationReason
    extra = 0
    fields = ("position", "type", "text", "weight", "detail")
    readonly_fields = fields


@admin.register(Recommendation)
class RecommendationAdmin(ReadOnlyAdmin[Recommendation]):
    list_display = (
        "developer",
        "rank",
        "repository",
        "match_label",
        "score",
        "scoring_config",
        "generated_at",
    )
    list_filter = ("match_label", "scoring_config")
    search_fields = ("repository__full_name",)
    readonly_fields = ("signal_scores", "technologies")
    inlines = [ReasonInline]
