from django.contrib import admin

from .models import GitHubAccount


@admin.register(GitHubAccount)
class GitHubAccountAdmin(admin.ModelAdmin[GitHubAccount]):
    list_display = ("username", "github_id", "user", "updated_at")
    # The encrypted token is deliberately excluded from the admin.
    exclude = ("access_token_encrypted",)
    readonly_fields = ("user", "github_id", "username", "avatar_url", "scopes")
