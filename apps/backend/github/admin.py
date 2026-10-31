from django.contrib import admin

from core.admin import NoAddDeleteAdmin

from .models import GitHubAccount, GitHubProfile


@admin.register(GitHubAccount)
class GitHubAccountAdmin(NoAddDeleteAdmin[GitHubAccount]):
    """Removing a connection goes through disconnect, which also revokes the token."""

    list_select_related = ("user",)
    list_display = ("username", "github_id", "user", "updated_at")
    # The encrypted token is deliberately excluded from the admin.
    exclude = ("access_token_encrypted",)
    readonly_fields = ("user", "github_id", "username", "avatar_url", "scopes")


@admin.register(GitHubProfile)
class GitHubProfileAdmin(NoAddDeleteAdmin[GitHubProfile]):
    """Removing GitHub data goes through delete-data."""

    list_select_related = ("user",)
    list_display = ("login", "user", "public_repos", "has_profile_readme", "synced_at")
    readonly_fields = [f.name for f in GitHubProfile._meta.fields]
