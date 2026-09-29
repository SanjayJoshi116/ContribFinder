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


def _weight_errors(name: str, weights: object, sources: list[str], code: str) -> list[CheckMessage]:
    if not isinstance(weights, dict):
        return [Error(f"{name} must be a mapping of source to weight.", id=code)]
    errors: list[CheckMessage] = []
    if missing := sorted(set(sources) - set(weights)):
        errors.append(Error(f"{name} is missing sources: {', '.join(missing)}.", id=code))
    if unknown := sorted(set(weights) - set(sources)):
        errors.append(Error(f"{name} has unknown sources: {', '.join(unknown)}.", id=code))
    for source, weight in weights.items():
        if not isinstance(weight, int | float) or isinstance(weight, bool) or not 0 <= weight <= 1:
            errors.append(Error(f"{name}[{source!r}] must be a number between 0 and 1.", id=code))
    return errors


@register()
def profiling_config_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Evidence weights are configuration (FR-PROFILE-005); refuse to start with bad values."""
    from developers.models import InterestSource, SkillSource

    errors = _weight_errors(
        "EVIDENCE_WEIGHTS", settings.EVIDENCE_WEIGHTS, SkillSource.values, "core.E010"
    )
    errors += _weight_errors(
        "INTEREST_EVIDENCE_WEIGHTS",
        settings.INTEREST_EVIDENCE_WEIGHTS,
        InterestSource.values,
        "core.E011",
    )
    for name in ("EVIDENCE_REPEAT_DECAY", "CONFIDENCE_CAP"):
        if not 0 < getattr(settings, name) < 1:
            errors.append(Error(f"{name} must be strictly between 0 and 1.", id="core.E012"))
    for name in ("LANGUAGE_MIN_SHARE", "INTEREST_MIN_STRENGTH"):
        if not 0 <= getattr(settings, name) <= 1:
            errors.append(Error(f"{name} must be between 0 and 1.", id="core.E013"))
    return errors
