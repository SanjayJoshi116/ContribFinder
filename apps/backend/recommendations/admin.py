from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import mark_safe

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

    def get_readonly_fields(
        self, request: HttpRequest, obj: ScoringConfig | None = None
    ) -> list[str] | tuple[str, ...]:
        # A stored version always means the same numbers (``ScoringConfig.save`` enforces it):
        # it may have been evaluated, recorded in baselines.json or snapshotted by feedback
        # without producing recommendations.
        if obj is not None:
            return (*self.readonly_fields, "version", "weights", "params", "activation")
        return self.readonly_fields

    @admin.display(description="Activation")
    def activation(self, obj: ScoringConfig) -> str:
        # Activation runs the benchmark comparison, which never happens inside a web request
        # (spec recommendation-evaluation, "Activating a configuration"): the page only names
        # the command.
        if obj.is_active:
            return mark_safe(
                "Active. To activate another configuration, run "
                "<code>npm run manage -- activate_scoring_config &lt;version&gt;</code>."
            )
        return format_html(
            "Run <code>npm run manage -- activate_scoring_config {}</code>. The command "
            "compares it with the active configuration on the selection benchmark first; add "
            '<code>--force --reason "..."</code> for a deliberate exception.',
            obj.version,
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
