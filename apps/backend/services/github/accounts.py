from dataclasses import dataclass

from django.db import transaction

from accounts.models import User
from github.models import GitHubAccount
from services.crypto import encrypt_token
from services.github.oauth import GitHubIdentity, TokenResult


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
    return LinkResult(user=user, created_user=created_user)
