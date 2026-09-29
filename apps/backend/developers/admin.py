from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from .models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    Interest,
    Skill,
    SkillEvidence,
)


class ReadOnlyAdmin[M: Model](admin.ModelAdmin[M]):
    """Derived data is rebuilt by analysis; editing it in the admin would be overwritten."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return False


@admin.register(DeveloperProfile)
class DeveloperProfileAdmin(ReadOnlyAdmin[DeveloperProfile]):
    list_display = ("user", "experience_level", "analyzed_at")


@admin.register(Skill)
class SkillAdmin(ReadOnlyAdmin[Skill]):
    list_display = ("name", "slug", "category")
    list_filter = ("category",)
    search_fields = ("name", "slug")


class SkillEvidenceInline(admin.TabularInline[SkillEvidence, DeveloperSkill]):
    model = SkillEvidence
    extra = 0
    can_delete = False
    readonly_fields = ("source", "repository", "detail", "observed_at")


@admin.register(DeveloperSkill)
class DeveloperSkillAdmin(ReadOnlyAdmin[DeveloperSkill]):
    list_display = ("profile", "skill", "confidence", "last_observed_at")
    inlines = [SkillEvidenceInline]


@admin.register(Interest)
class InterestAdmin(ReadOnlyAdmin[Interest]):
    list_display = ("name", "slug")


@admin.register(DeveloperInterest)
class DeveloperInterestAdmin(ReadOnlyAdmin[DeveloperInterest]):
    list_display = ("profile", "interest", "strength")
