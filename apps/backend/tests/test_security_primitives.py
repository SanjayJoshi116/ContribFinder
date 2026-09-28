import logging

import pytest
from cryptography.fernet import Fernet
from django.core.checks import Error
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from accounts.models import AuditEvent
from core.checks import token_encryption_keys_check
from core.logging import RedactSecretsFilter, redact
from services import audit
from services.crypto import TokenDecryptionError, decrypt_token, encrypt_token, validate_keys

TOKEN = "gho_16C7e42F292c6912E7710c838347Ae178B4a"


def test_encrypt_decrypt_round_trip() -> None:
    ciphertext = encrypt_token(TOKEN)
    assert ciphertext != TOKEN
    assert TOKEN not in ciphertext
    assert decrypt_token(ciphertext) == TOKEN


def test_key_rotation_old_key_still_decrypts() -> None:
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    with override_settings(TOKEN_ENCRYPTION_KEYS=[old_key]):
        old_ciphertext = encrypt_token(TOKEN)
    with override_settings(TOKEN_ENCRYPTION_KEYS=[new_key, old_key]):
        assert decrypt_token(old_ciphertext) == TOKEN
        new_ciphertext = encrypt_token(TOKEN)
    # New ciphertext is produced with the newest key only.
    with override_settings(TOKEN_ENCRYPTION_KEYS=[new_key]):
        assert decrypt_token(new_ciphertext) == TOKEN


def test_unknown_key_cannot_decrypt() -> None:
    ciphertext = encrypt_token(TOKEN)
    with (
        override_settings(TOKEN_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]),
        pytest.raises(TokenDecryptionError),
    ):
        decrypt_token(ciphertext)


@pytest.mark.parametrize("keys", [[], ["not-a-fernet-key"]])
def test_invalid_keys_rejected(keys: list[str]) -> None:
    with pytest.raises(ImproperlyConfigured):
        validate_keys(keys)
    with override_settings(TOKEN_ENCRYPTION_KEYS=keys):
        messages = token_encryption_keys_check()
    assert len(messages) == 1
    assert isinstance(messages[0], Error)
    assert messages[0].id == "core.E001"


@pytest.mark.django_db
def test_audit_record_stores_hashed_ip(user) -> None:
    class _Req:
        META = {"REMOTE_ADDR": "203.0.113.9"}

    event = audit.record(
        AuditEvent.Action.LOGOUT,
        AuditEvent.Outcome.SUCCESS,
        user=user,
        request=_Req(),  # type: ignore[arg-type]
        metadata={"github_username": "octocat"},
    )
    assert event.user == user
    assert event.ip_hash and "203.0.113.9" not in event.ip_hash
    assert event.metadata == {"github_username": "octocat"}


@pytest.mark.django_db
def test_audit_rejects_unlisted_metadata_keys() -> None:
    with pytest.raises(audit.DisallowedAuditMetadata):
        audit.record(
            AuditEvent.Action.SIGN_IN,
            AuditEvent.Outcome.SUCCESS,
            metadata={"access_token": TOKEN},
        )
    assert not AuditEvent.objects.exists()


@pytest.mark.parametrize(
    "line",
    [
        "POST /login/oauth/access_token body=client_id=x&client_secret=s3cr3t&code=abc123",
        f"token exchange returned {{'access_token': '{TOKEN}', 'scope': ''}}",
        f'{{"access_token": "{TOKEN}"}}',
        f"Authorization: token {TOKEN}",
        "callback ?code=abc123&state=xyz789",
    ],
)
def test_redact_masks_secrets(line: str) -> None:
    redacted = redact(line)
    for secret in (TOKEN, "s3cr3t", "abc123", "xyz789"):
        assert secret not in redacted


def test_redaction_filter_applies_to_args_and_exceptions() -> None:
    record = logging.LogRecord(
        "t", logging.ERROR, __file__, 1, "got %s", (f"access_token={TOKEN}",), None
    )
    try:
        raise ValueError(f"bad token {TOKEN}")
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()
    assert RedactSecretsFilter().filter(record)
    assert TOKEN not in record.getMessage()
    assert record.exc_text is not None
    assert TOKEN not in record.exc_text
