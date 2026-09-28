from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning, register
from django.core.exceptions import ImproperlyConfigured

from services.crypto import validate_keys


@register()
def token_encryption_keys_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    try:
        validate_keys(settings.TOKEN_ENCRYPTION_KEYS)
    except ImproperlyConfigured as exc:
        return [
            Error(
                str(exc),
                hint='Generate one with: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"',
                id="core.E001",
            )
        ]
    return []


@register()
def github_oauth_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        return [
            Warning(
                "GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET are not set; GitHub sign-in will fail.",
                id="core.W001",
            )
        ]
    return []
