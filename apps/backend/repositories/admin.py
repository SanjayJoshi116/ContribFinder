from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from .models import (
    CandidateDiscovery,
    Repository,
    RepositoryCandidate,
    RepositoryDependency,
    RepositoryLanguage,
    RepositorySnapshot,
    RepositoryTopic,
    UserRepository,
)


class ReadOnlyAdmin[M: Model](admin.ModelAdmin[M]):
    """Discovery data is rebuilt by background jobs; editing it here would be overwritten."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return False


class LanguageInline(admin.TabularInline[RepositoryLanguage, Repository]):
    model = RepositoryLanguage
    extra = 0


class TopicInline(admin.TabularInline[RepositoryTopic, Repository]):
    model = RepositoryTopic
    extra = 0


class DependencyInline(admin.TabularInline[RepositoryDependency, Repository]):
    model = RepositoryDependency
    extra = 0


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin[Repository]):
    list_display = (
        "full_name",
        "primary_language",
        "stars",
        "is_fork",
        "lifecycle",
        "is_eligible",
        "pushed_at",
    )
    list_filter = ("lifecycle", "is_eligible")
    search_fields = ("full_name",)
    inlines = [LanguageInline, TopicInline, DependencyInline]


@admin.register(UserRepository)
class UserRepositoryAdmin(admin.ModelAdmin[UserRepository]):
    list_display = ("user", "repository", "relation", "merged_pr_count", "linked_at")
    list_filter = ("relation",)


@admin.register(RepositorySnapshot)
class RepositorySnapshotAdmin(ReadOnlyAdmin[RepositorySnapshot]):
    list_display = ("repository", "captured_at", "activity_label", "commits_90d", "contributors")
    list_filter = ("activity_label",)
    search_fields = ("repository__full_name",)


class DiscoveryInline(admin.TabularInline[CandidateDiscovery, RepositoryCandidate]):
    model = CandidateDiscovery
    extra = 0
    can_delete = False
    readonly_fields = ("source", "query", "search_rank", "first_seen_at", "last_seen_at")


@admin.register(RepositoryCandidate)
class RepositoryCandidateAdmin(ReadOnlyAdmin[RepositoryCandidate]):
    list_display = ("developer", "repository", "first_discovered_at", "last_seen_at")
    search_fields = ("repository__full_name",)
    inlines = [DiscoveryInline]
