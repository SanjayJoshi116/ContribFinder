"""Audit trail for sensitive account actions (SRS-2 §64).

Metadata keys are allowlisted so a credential can never be stored by accident, and the
client IP is stored only as a salted hash.
"""

import hashlib
import hmac
from typing import Any

from django.conf import settings
from django.http import HttpRequest

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


class DisallowedAuditMetadata(ValueError):
    pass


def hash_ip(ip: str) -> str:
    if not ip:
        return ""
    salt = hashlib.sha256(f"audit-ip:{settings.SECRET_KEY}".encode()).digest()
    return hmac.new(salt, ip.encode(), hashlib.sha256).hexdigest()


def _client_ip(request: HttpRequest | None) -> str:
    if request is None:
        return ""
    return str(request.META.get("REMOTE_ADDR", ""))


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
        ip_hash=hash_ip(_client_ip(request)),
    )
