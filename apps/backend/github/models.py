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
