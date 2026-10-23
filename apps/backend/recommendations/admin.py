from django.contrib import admin, messages
from django.db.models import Model, QuerySet
from django.http import HttpRequest

from accounts.models import User
from services.ranking import activation

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
        version = queryset.get().version
        user = request.user if isinstance(request.user, User) else None
        try:
            # The same rule as the command, never forced (spec recommendation-evaluation,
            # "Activating a configuration").
            result = activation.activate(version, via="admin", user=user, request=request)
        except activation.ActivationRefused as refused:
            self.message_user(
                request,
                f"{version} was not activated: {'; '.join(refused.failures)}. For a deliberate "
                f"exception run `npm run manage -- activate_scoring_config {version} --force "
                '--reason "..."`.',
                messages.ERROR,
            )
            return
        except activation.ActivationError as exc:
            self.message_user(request, str(exc), messages.ERROR)
            return
        if not result.changed:
            self.message_user(request, f"{version} is already active.")
            return
        self.message_user(
            request, f"{version} is active; recommendations regenerate on the next refresh."
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
