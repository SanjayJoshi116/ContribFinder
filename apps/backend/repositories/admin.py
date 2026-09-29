from django.contrib import admin

from .models import Repository, RepositoryLanguage, RepositoryTopic, UserRepository


class LanguageInline(admin.TabularInline[RepositoryLanguage, Repository]):
    model = RepositoryLanguage
    extra = 0


class TopicInline(admin.TabularInline[RepositoryTopic, Repository]):
    model = RepositoryTopic
    extra = 0


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin[Repository]):
    list_display = ("full_name", "primary_language", "stars", "is_fork", "pushed_at")
    search_fields = ("full_name",)
    inlines = [LanguageInline, TopicInline]


@admin.register(UserRepository)
class UserRepositoryAdmin(admin.ModelAdmin[UserRepository]):
    list_display = ("user", "repository", "relation", "linked_at")
