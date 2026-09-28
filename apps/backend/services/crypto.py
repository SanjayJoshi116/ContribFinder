"""Encryption for credentials stored at rest (GitHub access tokens).

Every place that handles a plaintext token goes through these two functions, which keeps
plaintext handling easy to find. Keys come from ``settings.TOKEN_ENCRYPTION_KEYS``
(newest first); older keys remain valid for decryption so keys can be rotated.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class TokenDecryptionError(Exception):
    """Stored ciphertext could not be decrypted with any configured key."""


def validate_keys(keys: list[str] | tuple[str, ...]) -> None:
    if not keys:
        raise ImproperlyConfigured("TOKEN_ENCRYPTION_KEYS must contain at least one Fernet key.")
    for index, key in enumerate(keys):
        try:
            Fernet(key.strip().encode())
        except (ValueError, TypeError) as exc:
            raise ImproperlyConfigured(
                f"TOKEN_ENCRYPTION_KEYS entry #{index + 1} is not a valid Fernet key."
            ) from exc


@lru_cache(maxsize=4)
def _fernet(keys: tuple[str, ...]) -> MultiFernet:
    validate_keys(keys)
    return MultiFernet([Fernet(k.strip().encode()) for k in keys])


def _current() -> MultiFernet:
    return _fernet(tuple(settings.TOKEN_ENCRYPTION_KEYS))


def encrypt_token(plaintext: str) -> str:
    return _current().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _current().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenDecryptionError(
            "Stored token cannot be decrypted with configured keys."
        ) from exc
