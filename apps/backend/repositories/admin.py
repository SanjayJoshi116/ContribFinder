from django.contrib import admin

from .models import (
    Repository,
    RepositoryDependency,
    RepositoryLanguage,
    RepositoryTopic,
    UserRepository,
)


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
    list_display = ("full_name", "primary_language", "stars", "is_fork", "pushed_at")
    search_fields = ("full_name",)
    inlines = [LanguageInline, TopicInline, DependencyInline]


@admin.register(UserRepository)
class UserRepositoryAdmin(admin.ModelAdmin[UserRepository]):
    list_display = ("user", "repository", "relation", "merged_pr_count", "linked_at")
    list_filter = ("relation",)
