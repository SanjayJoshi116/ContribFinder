import logging
from dataclasses import dataclass

from django.db import transaction

from accounts.models import User
from github.models import GitHubAccount
from services.crypto import TokenDecryptionError, decrypt_token, encrypt_token
from services.github.oauth import GitHubIdentity, TokenResult, revoke_token

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinkResult:
    user: User
    created_user: bool


@transaction.atomic
def link_github_account(identity: GitHubIdentity, token: TokenResult) -> LinkResult:
    """Create or update the user and GitHub account for a successful sign-in.

    The user is keyed by GitHub ID (``gh_<id>``), so a user who disconnected and signs in
    again is re-linked to their existing account rather than duplicated.
    """
    user, created_user = User.objects.select_for_update().get_or_create(
        username=f"gh_{identity.github_id}",
        defaults={"display_name": identity.name},
    )
    if created_user:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif identity.name and user.display_name != identity.name:
        user.display_name = identity.name
        user.save(update_fields=["display_name"])

    previous = _stored_token(identity.github_id)
    GitHubAccount.objects.update_or_create(
        github_id=identity.github_id,
        defaults={
            "user": user,
            "username": identity.login,
            "avatar_url": identity.avatar_url,
            "access_token_encrypted": encrypt_token(token.access_token),
            "scopes": token.scopes,
        },
    )
    if previous and _plaintext(previous) not in (None, token.access_token):
        from github.tasks import revoke_replaced_token  # avoid import cycle

        # Off the request path: sign-in never waits on GitHub. Only ciphertext is queued.
        github_id = identity.github_id
        transaction.on_commit(lambda: revoke_replaced_token.delay(github_id, previous))
    return LinkResult(user=user, created_user=created_user)


def revoke_replaced(github_id: int, previous_encrypted: str) -> None:
    """Best effort: revoke the token a sign-in replaced (spec: github-authentication
    "Replaced token is revoked"), unless it is still the stored one. Never raises; logs the
    failure type only."""
    previous = _plaintext(previous_encrypted)
    if previous is None:
        return  # encrypted with a removed key: unusable for us, nothing to revoke with
    current = _stored_token(github_id)
    if current and _plaintext(current) == previous:
        return  # a later sign-in stored the same token again
    try:
        revoke_token(previous)
    except Exception as exc:
        logger.warning("Revoking the replaced GitHub token failed: %s", type(exc).__name__)


def _stored_token(github_id: int) -> str | None:
    return (
        GitHubAccount.objects.filter(github_id=github_id)
        .values_list("access_token_encrypted", flat=True)
        .first()
    )


def _plaintext(encrypted: str) -> str | None:
    """The token, or None when it was encrypted with a removed key."""
    try:
        return decrypt_token(encrypted)
    except TokenDecryptionError:
        return None
