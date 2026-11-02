from django.contrib import admin

from core.admin import ViewOnlyAdmin

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


class LanguageInline(admin.TabularInline[RepositoryLanguage, Repository]):
    model = RepositoryLanguage
    extra = 0
    can_delete = False


class TopicInline(admin.TabularInline[RepositoryTopic, Repository]):
    model = RepositoryTopic
    extra = 0
    can_delete = False


class DependencyInline(admin.TabularInline[RepositoryDependency, Repository]):
    model = RepositoryDependency
    extra = 0
    can_delete = False


@admin.register(Repository)
class RepositoryAdmin(ViewOnlyAdmin[Repository]):
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
class UserRepositoryAdmin(ViewOnlyAdmin[UserRepository]):
    list_display = ("user", "repository", "relation", "merged_pr_count", "linked_at")
    list_select_related = ("user", "repository")
    list_filter = ("relation",)


@admin.register(RepositorySnapshot)
class RepositorySnapshotAdmin(ViewOnlyAdmin[RepositorySnapshot]):
    list_display = ("repository", "captured_at", "activity_label", "commits_90d", "contributors")
    list_select_related = ("repository",)
    list_filter = ("activity_label",)
    search_fields = ("repository__full_name",)


class DiscoveryInline(admin.TabularInline[CandidateDiscovery, RepositoryCandidate]):
    model = CandidateDiscovery
    extra = 0
    can_delete = False
    readonly_fields = ("source", "query", "search_rank", "first_seen_at", "last_seen_at")


@admin.register(RepositoryCandidate)
class RepositoryCandidateAdmin(ViewOnlyAdmin[RepositoryCandidate]):
    list_display = ("developer", "repository", "first_discovered_at", "last_seen_at")
    list_select_related = ("developer", "repository")
    search_fields = ("repository__full_name",)
    inlines = [DiscoveryInline]
