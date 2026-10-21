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


@register()
def trusted_proxy_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    # Behind a TLS-terminating proxy with NUM_PROXIES=0, every request looks like plain HTTP
    # (redirect loop) and all clients share the proxy's throttle bucket.
    if settings.SECURE_SSL_REDIRECT and settings.NUM_PROXIES == 0:
        return [
            Warning(
                "SECURE_SSL_REDIRECT is on but NUM_PROXIES is 0: X-Forwarded-Proto and "
                "X-Forwarded-For are ignored.",
                hint="Behind a proxy or load balancer, set NUM_PROXIES to the number of proxies "
                "you control. Leave it at 0 only if this server terminates TLS itself.",
                id="core.W002",
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
STALE_PARTS = ("metadata", "readme", "community", "dependencies", "activity", "issues")
ISSUE_DIFFICULTY_KEYS = ("short_body", "long_body", "many_technologies", "long_discussion")
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


def _star_band_errors(bands: object) -> list[CheckMessage]:
    """Ascending, non-overlapping [low, high] bands; only the last may be open-ended (null);
    the first starts at DISCOVERY_MIN_STARS; the request budget covers one query in all."""

    def error(message: str) -> list[CheckMessage]:
        return [Error(f"DISCOVERY_STAR_BANDS: {message}", id="core.E025")]

    if not isinstance(bands, list) or not bands:
        return error("must be a non-empty list of [low, high] bands.")
    previous_high = -1
    for index, band in enumerate(bands):
        last = index == len(bands) - 1
        if not (isinstance(band, list) and len(band) == 2 and _is_int(band[0])):
            return error(f"band {index} must be [low, high] with an integer low.")
        low, high = band
        if high is None and not last:
            return error("only the last band can be open-ended (null).")
        if high is not None and (not _is_int(high) or high < low):
            return error(f"band {index} must have an integer high of at least its low.")
        if low <= previous_high:
            return error("bands must be ascending and must not overlap.")
        previous_high = high if high is not None else low
    if bands[0][0] != settings.DISCOVERY_MIN_STARS:
        return error("the first band must start at DISCOVERY_MIN_STARS.")
    if _is_int(settings.DISCOVERY_MAX_QUERIES) and len(bands) > settings.DISCOVERY_MAX_QUERIES:
        return error("DISCOVERY_MAX_QUERIES must be at least the number of bands.")
    return []


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
        "REPO_REFRESH_RETRY_MINUTES",
        "THROTTLE_CACHE_BACKOFF_SECONDS",
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
    errors += _star_band_errors(settings.DISCOVERY_STAR_BANDS)
    topics = settings.DISCOVERY_EXCLUDED_TOPICS
    if not isinstance(topics, list) or not all(isinstance(t, str) and t for t in topics):
        errors.append(
            Error("DISCOVERY_EXCLUDED_TOPICS must be a list of topic names.", id="core.E026")
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


@register()
def recommendation_config_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Top-N size, minimum score and size classes (Phase 5). Weights live in ScoringConfig rows
    and are validated there: a database check would run before migrations."""
    errors: list[CheckMessage] = []
    top_n = settings.RECOMMENDATIONS_TOP_N
    if not _is_int(top_n) or top_n < 20:
        errors.append(
            Error("RECOMMENDATIONS_TOP_N must be an integer of at least 20.", id="core.E030")
        )
    if not 0 <= settings.RECOMMENDATION_MIN_SCORE <= 1:
        errors.append(Error("RECOMMENDATION_MIN_SCORE must be between 0 and 1.", id="core.E031"))
    for name in ("RECOMMENDATION_REFRESH_INTERVAL_SECONDS", "RECOMMENDATION_README_EXCERPT_CHARS"):
        value = getattr(settings, name)
        if not _is_int(value) or value <= 0:
            errors.append(Error(f"{name} must be a positive integer.", id="core.E020"))
    sizes = settings.REPO_SIZE_THRESHOLDS
    size_errors = _keys_errors("REPO_SIZE_THRESHOLDS", sizes, ("small", "medium"), "core.E032")
    errors += size_errors
    if not size_errors and not 0 < sizes["small"] < sizes["medium"]:
        errors.append(
            Error(
                "REPO_SIZE_THRESHOLDS: small must be positive and lower than medium.",
                id="core.E032",
            )
        )
    return errors


@register()
def feedback_config_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """View de-duplication window (Phase 8a)."""
    value = settings.FEEDBACK_VIEW_DEDUP_MINUTES
    if not _is_int(value) or value <= 0:
        return [Error("FEEDBACK_VIEW_DEDUP_MINUTES must be a positive integer.", id="core.E020")]
    return []


@register()
def issue_config_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Issue fetch budget, body cap, age limit and difficulty thresholds (Phase 7)."""
    errors: list[CheckMessage] = []
    for name in ("ISSUES_MAX_PAGES", "ISSUE_BODY_MAX_CHARS", "ISSUE_MAX_AGE_DAYS"):
        value = getattr(settings, name)
        if not _is_int(value) or value <= 0:
            errors.append(Error(f"{name} must be a positive integer.", id="core.E020"))
    thresholds = settings.ISSUE_DIFFICULTY
    difficulty_errors = _keys_errors(
        "ISSUE_DIFFICULTY", thresholds, ISSUE_DIFFICULTY_KEYS, "core.E040"
    )
    errors += difficulty_errors
    if not difficulty_errors:
        if not 0 < thresholds["short_body"] < thresholds["long_body"]:
            errors.append(
                Error(
                    "ISSUE_DIFFICULTY: short_body must be positive and lower than long_body.",
                    id="core.E040",
                )
            )
        if thresholds["many_technologies"] < 2 or thresholds["long_discussion"] < 1:
            errors.append(
                Error(
                    "ISSUE_DIFFICULTY: many_technologies must be at least 2 and "
                    "long_discussion at least 1.",
                    id="core.E040",
                )
            )
    return errors
