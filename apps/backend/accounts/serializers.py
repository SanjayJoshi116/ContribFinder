from rest_framework import serializers

from .models import User


class MeSerializer(serializers.Serializer[User]):
    """Explicit allowlist: nothing credential-bearing can reach the client."""

    id = serializers.IntegerField(read_only=True)
    github_username = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    github_connected = serializers.SerializerMethodField()

    def _account(self, user: User):  # type: ignore[no-untyped-def]
        return getattr(user, "github_account", None)

    def get_github_username(self, user: User) -> str | None:
        account = self._account(user)
        return account.username if account else None

    def get_avatar_url(self, user: User) -> str | None:
        account = self._account(user)
        return account.avatar_url if account else None

    def get_github_connected(self, user: User) -> bool:
        return self._account(user) is not None


class DisconnectResultSerializer(serializers.Serializer[dict[str, str]]):
    revocation = serializers.ChoiceField(
        # "revoked" and "failed" are no longer returned (revocation is queued since 0.12.41).
        choices=["queued", "not_connected", "revoked", "failed"],
        help_text="Whether a GitHub revocation was queued. Local credentials are deleted at once.",
    )
