from django.contrib import admin

from .models import GitHubAccount, GitHubProfile


@admin.register(GitHubAccount)
class GitHubAccountAdmin(admin.ModelAdmin[GitHubAccount]):
    list_display = ("username", "github_id", "user", "updated_at")
    # The encrypted token is deliberately excluded from the admin.
    exclude = ("access_token_encrypted",)
    readonly_fields = ("user", "github_id", "username", "avatar_url", "scopes")


@admin.register(GitHubProfile)
class GitHubProfileAdmin(admin.ModelAdmin[GitHubProfile]):
    list_display = ("login", "user", "public_repos", "has_profile_readme", "synced_at")
    readonly_fields = [f.name for f in GitHubProfile._meta.fields]
