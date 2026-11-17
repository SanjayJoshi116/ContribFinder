import logging
from dataclasses import dataclass

from django.db import transaction

from accounts.models import AuditEvent, User
from github.models import GitHubAccount
from services import audit, dispatch
from services.crypto import TokenDecryptionError, decrypt_token, encrypt_token
from services.github.oauth import GitHubIdentity, TokenResult, revoke_grant, revoke_token

logger = logging.getLogger(__name__)


class AccountInactive(Exception):
    """The GitHub user's account was deactivated: sign-in is refused, nothing is stored."""


@dataclass(frozen=True)
class LinkResult:
    user: User
    created_user: bool


@transaction.atomic
def link_github_account(identity: GitHubIdentity, token: TokenResult) -> LinkResult:
    """Create or update the user and GitHub account for a successful sign-in.

    The user is keyed by GitHub ID (``gh_<id>``), so a user who disconnected and signs in
    again is re-linked to their existing account rather than duplicated. A deactivated user
    raises ``AccountInactive`` before anything is written.
    """
    user, created_user = User.objects.select_for_update().get_or_create(
        username=f"gh_{identity.github_id}",
        defaults={"display_name": identity.name},
    )
    if not user.is_active:
        raise AccountInactive()
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
        queue_revocation(previous, identity.github_id, grant=False)
    return LinkResult(user=user, created_user=created_user)


def queue_revocation(encrypted: str, github_id: int | None, *, grant: bool) -> None:
    """Revoke a token off the request path, once the caller's transaction commits. Only
    ciphertext is queued. A broker refusal is logged, never raised into the caller
    (``services.dispatch``)."""
    from github.tasks import revoke_later  # avoid import cycle

    dispatch.after_commit(
        revoke_later, encrypted, github_id, grant, about="token revocation", robust=True
    )


def revoke(encrypted: str, github_id: int | None, *, grant: bool) -> None:
    """Revoke the grant (``grant``) or this one token. With ``github_id``, the account's current
    link decides: a token still stored is never revoked, and once the user has signed in again
    the grant is in use, so only this token goes. Raises for the task's retry policy."""
    token = _plaintext(encrypted)
    if token is None:
        logger.warning("GitHub revocation skipped: the token's encryption key was removed")
        return
    current = _stored_token(github_id) if github_id is not None else None
    if current is not None:
        if _plaintext(current) == token:
            return
        grant = False
    (revoke_grant if grant else revoke_token)(token)


def record_revocation_failure(code: str) -> None:
    """The final failure of a queued revocation, without the token or who it was for. Logged
    by the task (``log_failure``); this only audits it."""
    audit.record(
        AuditEvent.Action.GITHUB_REVOCATION_FAILED,
        AuditEvent.Outcome.FAILURE,
        metadata={"reason": code},
    )


def refuse_token(access_token: str) -> None:
    """Revoke the grant of a refused sign-in (deactivated user) in the background."""
    queue_revocation(encrypt_token(access_token), None, grant=True)


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
