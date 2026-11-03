from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from core.admin import NoAddDeleteAdmin, ViewOnlyAdmin

from .models import Recommendation, RecommendationReason, ScoringConfig


@admin.register(ScoringConfig)
class ScoringConfigAdmin(NoAddDeleteAdmin[ScoringConfig]):
    # Configurations are stored by seed migrations only (``_seeding.store_inactive``); a deleted
    # version could be stored again with other numbers, and the active one must stay. Change
    # stays for the description: the fixed fields are read-only below.
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
    can_delete = False


@admin.register(Recommendation)
class RecommendationAdmin(ViewOnlyAdmin[Recommendation]):
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
    list_select_related = ("developer", "repository", "scoring_config")
    search_fields = ("repository__full_name",)
    inlines = [ReasonInline]
