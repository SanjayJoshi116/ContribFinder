"""Audit trail for sensitive account actions (SRS-2 §64).

Metadata keys are allowlisted so a credential can never be stored by accident, and the
client IP is stored only as a salted hash.
"""

import hashlib
import hmac
from typing import Any

from django.conf import settings
from django.db.models.expressions import RawSQL
from django.http import HttpRequest
from rest_framework.throttling import BaseThrottle

from accounts.models import AuditEvent, User

ALLOWED_METADATA_KEYS = frozenset(
    {
        "github_id",
        "github_username",
        "reason",
        "error_code",
        "revocation",
        "created_user",
        "deleted",  # counts of deleted rows per kind, never content
    }
)


# Allowed metadata that identifies the person; removed when their account is deleted.
IDENTIFYING_METADATA_KEYS = frozenset({"github_id", "github_username"})


class DisallowedAuditMetadata(ValueError):
    pass


def hash_ip(ip: str) -> str:
    if not ip:
        return ""
    salt = hashlib.sha256(f"audit-ip:{settings.SECRET_KEY}".encode()).digest()
    return hmac.new(salt, ip.encode(), hashlib.sha256).hexdigest()


def client_ip(request: HttpRequest) -> str:
    """The client address exactly as DRF throttling identifies it (REST_FRAMEWORK NUM_PROXIES)."""
    # get_ident reads only headers and META, which a plain HttpRequest has.
    return str(BaseThrottle().get_ident(request) or "")  # type: ignore[arg-type]


def record(
    action: str,
    outcome: str,
    *,
    user: User | None = None,
    request: HttpRequest | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    metadata = metadata or {}
    disallowed = set(metadata) - ALLOWED_METADATA_KEYS
    if disallowed:
        raise DisallowedAuditMetadata(f"Audit metadata keys not allowed: {sorted(disallowed)}")
    if user is not None and not user.is_authenticated:
        user = None
    return AuditEvent.objects.create(
        user=user,
        action=action,
        outcome=outcome,
        metadata=metadata,
        ip_hash=hash_ip(client_ip(request) if request else ""),
    )


def anonymize_user_entries(user: User) -> None:
    """Strip identifying values from the user's entries before the account is deleted
    (spec: data-controls "Audit of data deletion"). Action, outcome, time, reasons and
    counts stay; the user link goes with the account (SET_NULL)."""
    AuditEvent.objects.filter(user=user).update(
        ip_hash="",
        metadata=RawSQL("metadata - %s::text[]", (sorted(IDENTIFYING_METADATA_KEYS),)),
    )
