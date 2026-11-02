from collections.abc import Callable, Iterable
from typing import Any, TypeGuard

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning, register
from django.core.exceptions import ImproperlyConfigured

from services.crypto import validate_keys
from services.github.oauth import has_app_credentials
from services.issues.classify import LEVEL_VOTERS, MAX_LEVEL_VOTES
from services.profiling.experience import SIGNALS as EXPERIENCE_SIGNALS


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
    if not has_app_credentials():
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


@register()
def content_security_policy_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return [
        Error(f"{name} must be a non-empty single-line string (core.csp).", id="core.E060")
        for name in ("CONTENT_SECURITY_POLICY_API", "CONTENT_SECURITY_POLICY_HTML")
        if not isinstance(value := getattr(settings, name, None), str)
        or not value.strip()
        # Django refuses header values with control characters (BadHeaderError).
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ]


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
        value = getattr(settings, name)
        if not _is_number(value) or not 0 < value < 1:
            errors.append(Error(f"{name} must be strictly between 0 and 1.", id="core.E012"))
    for name in ("LANGUAGE_MIN_SHARE", "INTEREST_MIN_STRENGTH"):
        if not _between(getattr(settings, name), 0, 1):
            errors.append(Error(f"{name} must be between 0 and 1.", id="core.E013"))
    return errors + _experience_errors(settings.EXPERIENCE_THRESHOLDS)


def _experience_pair(pair: object) -> bool:
    return (
        isinstance(pair, list | tuple)
        and len(pair) == 2
        and all(_is_number(v) and v >= 0 for v in pair)
        and pair[0] <= pair[1]
    )


def _experience_errors(thresholds: object) -> list[CheckMessage]:
    """Per signal ``[intermediate_from, experienced_from]``; anything else fails every analysis."""
    return _keys_errors(
        "EXPERIENCE_THRESHOLDS",
        thresholds,
        EXPERIENCE_SIGNALS,
        "core.E014",
        item_ok=_experience_pair,
        item_rule="[intermediate_from, experienced_from]: two non-negative numbers, the first "
        "not above the second",
    )


ISSUE_DIFFICULTY_KEYS = (
    "short_body",
    "long_body",
    "several_technologies",
    "many_technologies",
    "long_discussion",
    "min_votes",
)
ACTIVITY_KEYS = (
    "recent_push_days",
    "recent_commits",
    "recent_merged_prs",
    "moderate_push_days",
    "moderate_commits",
    "moderate_merged_prs",
)


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _between(value: object, low: float, high: float) -> bool:
    """A number in [low, high]; anything else (None, a string) is out of range."""
    return _is_number(value) and low <= value <= high


# Scalar rules: (predicate, what the value must be, check id).
Rule = tuple[Callable[[object], bool], str, str]
POSITIVE_INT: Rule = (lambda v: _is_int(v) and v > 0, "a positive integer", "core.E020")
NON_NEGATIVE_INT: Rule = (lambda v: _is_int(v) and v >= 0, "a non-negative integer", "core.E050")
POSITIVE_NUMBER: Rule = (lambda v: _is_number(v) and v > 0, "a positive number", "core.E051")


def _rule_errors(names: Iterable[str], rule: Rule) -> list[CheckMessage]:
    ok, what, code = rule
    return [Error(f"{n} must be {what}.", id=code) for n in names if not ok(getattr(settings, n))]


def _keys_errors(
    name: str,
    value: object,
    keys: tuple[str, ...],
    code: str,
    item_ok: Callable[[object], bool] = NON_NEGATIVE_INT[0],
    item_rule: str = "a non-negative integer",
) -> list[CheckMessage]:
    if not isinstance(value, dict):
        return [Error(f"{name} must be a mapping.", id=code)]
    errors: list[CheckMessage] = []
    if missing := sorted(set(keys) - set(value)):
        errors.append(Error(f"{name} is missing keys: {', '.join(missing)}.", id=code))
    if unknown := sorted(set(value) - set(keys)):
        errors.append(Error(f"{name} has unknown keys: {', '.join(unknown)}.", id=code))
    for key, item in value.items():
        if not item_ok(item):
            errors.append(Error(f"{name}[{key!r}] must be {item_rule}.", id=code))
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
    errors = _rule_errors(
        (
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
            "RECOMMENDATION_FAILED_RETRY_MINUTES",
            "THROTTLE_CACHE_BACKOFF_SECONDS",
        ),
        POSITIVE_INT,
    )
    if not _is_int(settings.DISCOVERY_MIN_STARS) or settings.DISCOVERY_MIN_STARS < 0:
        errors.append(Error("DISCOVERY_MIN_STARS must be a non-negative integer.", id="core.E020"))
    per_query = settings.DISCOVERY_RESULTS_PER_QUERY
    if _is_int(per_query) and per_query > 100:
        errors.append(
            Error("DISCOVERY_RESULTS_PER_QUERY cannot exceed 100 (one page).", id="core.E021")
        )
    if not _between(settings.DISCOVERY_MIN_SKILL_CONFIDENCE, 0, 1):
        errors.append(
            Error("DISCOVERY_MIN_SKILL_CONFIDENCE must be between 0 and 1.", id="core.E013")
        )
    # Imported here: these modules need the app registry.
    from services.discovery.queries import STRATEGIES, configured_star_bands
    from services.repositories.staleness import PARTS

    shares = settings.DISCOVERY_QUERY_SHARES
    share_errors = _keys_errors("DISCOVERY_QUERY_SHARES", shares, STRATEGIES, "core.E022")
    errors += share_errors
    if not share_errors and sum(shares.values()) <= 0:
        errors.append(Error("DISCOVERY_QUERY_SHARES must have a positive total.", id="core.E022"))

    bands = configured_star_bands()
    band_errors = _star_band_errors(bands)
    errors += band_errors
    if not band_errors and _is_int(settings.DISCOVERY_MAX_QUERIES):
        unused = settings.DISCOVERY_MAX_QUERIES % len(bands)
        if unused:
            errors.append(
                Warning(
                    f"DISCOVERY_MAX_QUERIES leaves {unused} search request(s) unused: every "
                    f"query runs in all {len(bands)} star bands.",
                    hint="Use a multiple of the number of DISCOVERY_STAR_BANDS.",
                    id="core.W003",
                )
            )
    topics = settings.DISCOVERY_EXCLUDED_TOPICS
    if not isinstance(topics, list) or not all(isinstance(t, str) and t for t in topics):
        errors.append(
            Error("DISCOVERY_EXCLUDED_TOPICS must be a list of topic names.", id="core.E026")
        )
    errors += _keys_errors(
        "REPO_STALE_AFTER",
        settings.REPO_STALE_AFTER,
        PARTS,
        "core.E023",
        item_ok=POSITIVE_INT[0],
        item_rule="a positive integer",
    )
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
    if not _between(settings.RECOMMENDATION_MIN_SCORE, 0, 1):
        errors.append(Error("RECOMMENDATION_MIN_SCORE must be between 0 and 1.", id="core.E031"))
    errors += _rule_errors(
        ("RECOMMENDATION_REFRESH_INTERVAL_SECONDS", "RECOMMENDATION_README_EXCERPT_CHARS"),
        POSITIVE_INT,
    )
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
    return _rule_errors(("FEEDBACK_VIEW_DEDUP_MINUTES",), POSITIVE_INT)


@register()
def issue_config_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Issue fetch budget, entry labels, body cap, age limit and difficulty thresholds."""
    errors = _rule_errors(
        ("ISSUES_MAX_PAGES", "ISSUE_BODY_MAX_CHARS", "ISSUE_MAX_AGE_DAYS"), POSITIVE_INT
    )
    errors += _entry_label_errors(settings.ISSUES_ENTRY_LABELS)
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
        if not 2 <= thresholds["several_technologies"] <= thresholds["many_technologies"]:
            errors.append(
                Error(
                    "ISSUE_DIFFICULTY: several_technologies must be at least 2 and at most "
                    "many_technologies.",
                    id="core.E040",
                )
            )
        if not 2 <= thresholds["min_votes"] <= MAX_LEVEL_VOTES:
            errors.append(
                Error(
                    f"ISSUE_DIFFICULTY: min_votes must be at least 2 and at most "
                    f"{MAX_LEVEL_VOTES} (the most votes one difficulty level can get).",
                    id="core.E040",
                )
            )
        elif unreachable := [
            str(level)
            for level, voters in LEVEL_VOTERS.items()
            if len(voters) < thresholds["min_votes"]
        ]:
            errors.append(
                Warning(
                    f"ISSUE_DIFFICULTY: with min_votes {thresholds['min_votes']} no issue can be "
                    f"classified {' or '.join(unreachable)}.",
                    id="core.W004",
                )
            )
    return errors


def _entry_label_errors(labels: object) -> list[CheckMessage]:
    """A list of distinct (case-insensitive) label names, non-empty, without surrounding
    spaces (GitHub matches names exactly) and without commas (``labels=a,b`` asks for issues
    carrying both); empty fetches none."""
    if not isinstance(labels, list) or not all(
        isinstance(x, str) and x and x == x.strip() and "," not in x for x in labels
    ):
        return [Error("ISSUES_ENTRY_LABELS must be a list of label names.", id="core.E041")]
    if len({x.lower() for x in labels}) < len(labels):
        return [Error("ISSUES_ENTRY_LABELS names a label twice.", id="core.E041")]
    return []


# Integer settings where 0 would loop, never finish or never fetch anything.
POSITIVE_INT_SETTINGS = (
    "SYNC_MAX_ATTEMPTS",
    "SYNC_STALE_AFTER_SECONDS",
    "JOB_RECOVERY_INTERVAL_SECONDS",
    "GITHUB_SYNC_MAX_REPOS",
    "GITHUB_MAX_PAGES",
    "GITHUB_MAX_RETRY_DELAY",
    "GITHUB_ETAG_TTL",
    "GITHUB_ETAG_MAX_BYTES",
    "GITHUB_CACHE_BACKOFF_SECONDS",
    "GITHUB_MANIFEST_MAX_REPOS",
    "GITHUB_MANIFEST_MAX_BYTES",
    "GITHUB_CONTRIB_MAX_PRS",
    "GITHUB_CONTRIB_MAX_REPOS",
    "OAUTH_STATE_MAX_PENDING",
    "OAUTH_STATE_TTL_SECONDS",
    "REPO_FAILED_RETRY_HOURS",
    "REPEATED_CONTRIBUTION_MIN_PRS",
    "DISCOVERY_ANALYSIS_CONCURRENCY",
    "SESSION_COOKIE_AGE",
)
# 0 is meaningful: no cooldown, no grace period.
# NUM_PROXIES: 0 trusts no forwarded header; a negative count would index forwarded addresses
# wrongly (500s, or a client-chosen address).
NON_NEGATIVE_INT_SETTINGS = (
    "SYNC_COOLDOWN_SECONDS",
    "REPO_DISCOVERED_GRACE_MINUTES",
    "NUM_PROXIES",
)
POSITIVE_NUMBER_SETTINGS = ("GITHUB_HTTP_TIMEOUT", "REDIS_SOCKET_TIMEOUT")


@register()
def sync_github_config_check(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """Job, sync, GitHub client, OAuth and session limits."""
    return (
        _rule_errors(POSITIVE_INT_SETTINGS, POSITIVE_INT)
        + _rule_errors(NON_NEGATIVE_INT_SETTINGS, NON_NEGATIVE_INT)
        + _rule_errors(POSITIVE_NUMBER_SETTINGS, POSITIVE_NUMBER)
    )
