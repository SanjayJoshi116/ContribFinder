"""Leaving: deleting GitHub data, disconnecting GitHub and deleting the account (specs:
data-controls "Delete GitHub-derived data", github-authentication "Disconnect GitHub",
data-controls "Delete account"). The views add only the session handling.

GitHub is never called here: revocation is queued with the token encrypted, after the
transaction commits (invariant 3); a broker failure never stops the disconnect or deletion.
"""

from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest

from accounts.models import AuditEvent, User
from github.models import GitHubAccount
from services import audit, data_deletion
from services.github.accounts import queue_revocation


def _unlink(user: User) -> str:
    """Delete the stored credential now and queue its revocation once committed."""
    account = GitHubAccount.objects.filter(user=user).first()
    if account is None:
        return "not_connected"
    account.delete()
    queue_revocation(account.access_token_encrypted, account.github_id, grant=True)
    return "queued"


def _leave(user: User, request: HttpRequest, action: str) -> str:
    """What disconnecting and deleting share: unlink, delete the data, audit."""
    revocation = _unlink(user)
    deleted = data_deletion.delete_github_data(user)
    audit.record(
        action,
        AuditEvent.Outcome.SUCCESS,
        user=user,
        request=request,
        metadata={"revocation": revocation, "deleted": deleted},
    )
    return revocation


@transaction.atomic
def delete_github_data(user: User, request: HttpRequest) -> None:
    """Delete the user's GitHub-derived data and record it, all or nothing: a failing audit
    write leaves the data in place. The account and the GitHub connection stay."""
    deleted = data_deletion.delete_github_data(user)
    audit.record(
        AuditEvent.Action.GITHUB_DATA_DELETED,
        AuditEvent.Outcome.SUCCESS,
        user=user,
        request=request,
        metadata={"deleted": deleted},
    )


@transaction.atomic
def disconnect_github(user: User, request: HttpRequest) -> str:
    """Unlink GitHub and delete the user's GitHub data; returns the revocation state. A new
    unusable password changes the session auth hash, so every other session ends too."""
    revocation = _leave(user, request, AuditEvent.Action.GITHUB_DISCONNECT)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return revocation


@transaction.atomic
def delete_account(user: User, request: HttpRequest) -> None:
    """Unlink GitHub, delete the data, record, anonymize and delete the user, all or nothing:
    a failing delete leaves no "deleted" entry and the trail as it was. The entry is recorded
    while the user still exists and loses its user link with it (SET_NULL)."""
    _leave(user, request, AuditEvent.Action.ACCOUNT_DELETED)
    audit.anonymize_user_entries(user)
    user.delete()
