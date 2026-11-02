from django.contrib import admin

from core.admin import ViewOnlyAdmin

from .models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    Interest,
    InterestEvidence,
    Skill,
    SkillEvidence,
)


@admin.register(DeveloperProfile)
class DeveloperProfileAdmin(ViewOnlyAdmin[DeveloperProfile]):
    list_display = ("user", "experience_level", "analyzed_at")
    list_select_related = ("user",)


@admin.register(Skill)
class SkillAdmin(ViewOnlyAdmin[Skill]):
    list_display = ("name", "slug", "category")
    list_filter = ("category",)
    search_fields = ("name", "slug")


class SkillEvidenceInline(admin.TabularInline[SkillEvidence, DeveloperSkill]):
    model = SkillEvidence
    extra = 0
    can_delete = False
    readonly_fields = ("source", "repository", "detail", "observed_at")


@admin.register(DeveloperSkill)
class DeveloperSkillAdmin(ViewOnlyAdmin[DeveloperSkill]):
    list_display = ("profile", "skill", "confidence", "last_observed_at")
    list_select_related = ("profile", "skill")
    inlines = [SkillEvidenceInline]


@admin.register(Interest)
class InterestAdmin(ViewOnlyAdmin[Interest]):
    list_display = ("name", "slug")


class InterestEvidenceInline(admin.TabularInline[InterestEvidence, DeveloperInterest]):
    model = InterestEvidence
    extra = 0
    can_delete = False
    readonly_fields = ("source", "repository", "detail", "observed_at")


@admin.register(DeveloperInterest)
class DeveloperInterestAdmin(ViewOnlyAdmin[DeveloperInterest]):
    list_display = ("profile", "interest", "strength")
    list_select_related = ("profile", "interest")
    inlines = [InterestEvidenceInline]
