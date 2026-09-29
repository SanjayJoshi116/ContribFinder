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


QUERY_STRATEGIES = ("language", "skill", "interest", "topic")
STALE_PARTS = ("metadata", "readme", "community", "dependencies", "activity")
ACTIVITY_KEYS = (
    "recent_push_days",
    "recent_commits",
    "recent_merged_prs",
    "moderate_push_days",
    "moderate_commits",
    "moderate_merged_prs",
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _keys_errors(name: str, value: object, keys: tuple[str, ...], code: str) -> list[CheckMessage]:
    if not isinstance(value, dict):
        return [Error(f"{name} must be a mapping.", id=code)]
    errors: list[CheckMessage] = []
    if missing := sorted(set(keys) - set(value)):
        errors.append(Error(f"{name} is missing keys: {', '.join(missing)}.", id=code))
    if unknown := sorted(set(value) - set(keys)):
        errors.append(Error(f"{name} has unknown keys: {', '.join(unknown)}.", id=code))
    for key, item in value.items():
        if not _is_int(item) or item < 0:
            errors.append(Error(f"{name}[{key!r}] must be a non-negative integer.", id=code))
    return errors


@register()
def discovery_config_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Discovery budgets, staleness and activity thresholds are configuration (Phase 4)."""
    errors: list[CheckMessage] = []
    for name in (
        "DISCOVERY_MAX_QUERIES",
        "DISCOVERY_RESULTS_PER_QUERY",
        "DISCOVERY_MAX_ANALYSES_PER_RUN",
        "DISCOVERY_MAX_POOL",
        "DISCOVERY_CANDIDATE_RETENTION_DAYS",
        "DISCOVERY_MAX_PUSH_AGE_DAYS",
        "REPO_README_MAX_BYTES",
        "REPO_SNAPSHOT_HISTORY",
        "REPO_REFRESH_BATCH",
    ):
        value = getattr(settings, name)
        if not _is_int(value) or value <= 0:
            errors.append(Error(f"{name} must be a positive integer.", id="core.E020"))
    if not _is_int(settings.DISCOVERY_MIN_STARS) or settings.DISCOVERY_MIN_STARS < 0:
        errors.append(Error("DISCOVERY_MIN_STARS must be a non-negative integer.", id="core.E020"))
    if settings.DISCOVERY_RESULTS_PER_QUERY > 100:
        errors.append(
            Error("DISCOVERY_RESULTS_PER_QUERY cannot exceed 100 (one page).", id="core.E021")
        )
    if not 0 <= settings.DISCOVERY_MIN_SKILL_CONFIDENCE <= 1:
        errors.append(
            Error("DISCOVERY_MIN_SKILL_CONFIDENCE must be between 0 and 1.", id="core.E013")
        )
    errors += _keys_errors(
        "DISCOVERY_QUERY_SHARES", settings.DISCOVERY_QUERY_SHARES, QUERY_STRATEGIES, "core.E022"
    )
    errors += _keys_errors("REPO_STALE_AFTER", settings.REPO_STALE_AFTER, STALE_PARTS, "core.E023")
    thresholds = settings.ACTIVITY_THRESHOLDS
    activity_errors = _keys_errors("ACTIVITY_THRESHOLDS", thresholds, ACTIVITY_KEYS, "core.E024")
    errors += activity_errors
    if not activity_errors and (
        thresholds["moderate_push_days"] < thresholds["recent_push_days"]
        or thresholds["moderate_commits"] > thresholds["recent_commits"]
        or thresholds["moderate_merged_prs"] > thresholds["recent_merged_prs"]
    ):
        errors.append(
            Error(
                "ACTIVITY_THRESHOLDS: moderate thresholds cannot be stricter than recent ones.",
                id="core.E024",
            )
        )
    return errors
