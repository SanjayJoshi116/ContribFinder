from django.conf import settings
from django.db import models


class GitHubAccount(models.Model):
    """GitHub identity and credential, isolated from profile data (SRS-2 §43).

    ``access_token_encrypted`` holds Fernet ciphertext only. Use
    ``services.crypto.encrypt_token`` / ``decrypt_token``; never serialize this field.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="github_account"
    )
    github_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255)
    avatar_url = models.URLField(max_length=500, blank=True)
    access_token_encrypted = models.TextField()
    scopes = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"GitHubAccount({self.username}, id={self.github_id})"

    def __repr__(self) -> str:
        return f"<GitHubAccount username={self.username!r} github_id={self.github_id}>"


class GitHubProfile(models.Model):
    """Raw GitHub profile data from the last sync (SRS-2 §10-11).

    ``profile_readme`` is stored exactly as fetched; anything derived from it (skills,
    interests) lives in the developers app (Phase 3), never here.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="github_profile"
    )
    github_id = models.BigIntegerField()
    login = models.CharField(max_length=255)
    name = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    company = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    blog = models.CharField(max_length=500, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    followers = models.PositiveIntegerField(default=0)
    following = models.PositiveIntegerField(default=0)
    public_repos = models.PositiveIntegerField(default=0)
    github_created_at = models.DateTimeField(null=True, blank=True)
    has_profile_readme = models.BooleanField(default=False)
    profile_readme = models.TextField(blank=True)
    synced_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"GitHubProfile({self.login})"
