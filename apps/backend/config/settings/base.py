import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import django_stubs_ext
import environ
from django.core.exceptions import ImproperlyConfigured

# Allow generic annotations such as ModelAdmin[Model] / Serializer[T] at runtime.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent.parent

env = environ.Env()


def _dotenv_value(path: Path, key: str) -> str | None:
    """One value of a .env file, parsed by django-environ, without touching os.environ."""

    class Values(environ.Env):  # type: ignore[misc]  # django-environ is untyped
        ENVIRON: dict[str, str] = {}

    Values.read_env(path)
    return Values.ENVIRON.get(key)


# Local (non-Docker) runs read the repo-root .env; in Docker, compose injects it. The browser-test
# runner (scripts/e2e-backend.mjs) turns it off with DJANGO_READ_DOTENV=0; the test settings set
# DATABASE_URL: only the local database is taken from it, so tests see CI's settings otherwise.
_DOTENV = REPO_ROOT / ".env"
if _DOTENV.exists():
    if env.str("DJANGO_READ_DOTENV", default="").strip().upper() == "DATABASE_URL":
        _database_url = _dotenv_value(_DOTENV, "DATABASE_URL")
        if _database_url:
            os.environ.setdefault("DATABASE_URL", _database_url)
    elif env.bool("DJANGO_READ_DOTENV", default=True):
        env.read_env(_DOTENV)


def env_list(name: str, default: list[str]) -> list[str]:
    """A comma-separated setting, items trimmed and empty ones dropped: ``env.list`` keeps the
    space in ``a, b``, so " b" would match no host, origin, key or label."""
    return [item.strip() for item in env.list(name, default=default) if item.strip()]


def env_words(name: str) -> list[str]:
    """A list setting separated by spaces or commas (``a b``, ``a,b`` or ``a, b``); comma-only
    lists, whose items may contain spaces, use ``env_list``."""
    return [word for word in re.split(r"[\s,]+", env.str(name, default="")) if word]


def env_json(name: str, default: Any) -> Any:
    """A JSON setting; invalid JSON stops startup naming the setting (``env.json`` would raise
    a bare ``ValueError``). The system checks validate the shape."""
    if not env.str(name, default="").strip():
        return default  # unset or blank, as `NAME=` in a .env
    try:
        return env.json(name, default=default)
    except ValueError:
        raise ImproperlyConfigured(f"{name} is not valid JSON.") from None


def env_mapping[T](name: str, defaults: dict[str, T]) -> dict[str, T]:
    """A JSON object setting merged over ``defaults`` (one key overrides one default). Anything
    but a JSON object stops startup naming the setting, before the system checks run."""
    value = env_json(name, {})
    if not isinstance(value, dict):
        raise ImproperlyConfigured(f"{name} must be a JSON object, e.g. '{{\"key\": 1}}'.")
    return {**defaults, **value}


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "accounts",
    "core",
    "github",
    "jobs",
    "repositories",
    "developers",
    "recommendations",
    "feedback",
    "issues",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.csp.ContentSecurityPolicyMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Data stores -----------------------------------------------------------
# Default: locally installed PostgreSQL (`npm start`, no Docker). Docker/CI/production
# set DATABASE_URL explicitly.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://contribfinder:contribfinder@localhost:5432/contribfinder",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
# A reused connection is checked first, so one dropped by a database restart reconnects.
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Without REDIS_URL: in-process cache and eager (inline) Celery tasks. Fine for local
# development only; Docker and production always set REDIS_URL.
REDIS_URL = env("REDIS_URL", default="")
# Seconds before a Redis call gives up. Without it a stalled connection (e.g. a sleeping WSL
# distro) blocks a worker forever instead of failing the task.
REDIS_SOCKET_TIMEOUT = env.float("REDIS_SOCKET_TIMEOUT", default=5.0)
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "socket_timeout": REDIS_SOCKET_TIMEOUT,
                "socket_connect_timeout": REDIS_SOCKET_TIMEOUT,
            },
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# Users only sign in through GitHub; passwords are unusable. Validators kept for admin users.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Sessions / CSRF / CORS ------------------------------------------------
# Database sessions: a signed-in request never depends on the cache (Redis) being up.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=int(timedelta(days=14).total_seconds()))

# The SPA reads the CSRF cookie and echoes it in X-CSRFToken.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", default=[])
CSRF_FAILURE_VIEW = "core.views.csrf_failure"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"

# --- Security headers ------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# core.csp: the API's JSON loads nothing; HTML (the admin, error pages) only from this origin.
# The admin sets a few inline style attributes; its scripts are files. The SPA's own policy is
# written into its build (apps/frontend/csp.config.ts).
CONTENT_SECURITY_POLICY_API = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
CONTENT_SECURITY_POLICY_HTML = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)

# --- Trusted proxies -------------------------------------------------------
# Number of proxies in front of the app that append to X-Forwarded-For (e.g. 1 for the Vite dev
# proxy or a TLS-terminating load balancer). 0 trusts no forwarded header: client identity for
# throttling and audit is the connecting address, and X-Forwarded-Proto is ignored.
NUM_PROXIES = env.int("NUM_PROXIES", default=0)

# Production sets this: the web server and workers run system checks and refuse to start on errors.
RUN_STARTUP_CHECKS = False

# Seconds a process stops using the cache for throttling after a cache error (it lets
# requests through meanwhile instead of waiting for the Redis timeout on each one).
THROTTLE_CACHE_BACKOFF_SECONDS = env.int("THROTTLE_CACHE_BACKOFF_SECONDS", default=30)

# --- DRF / OpenAPI ---------------------------------------------------------
REST_FRAMEWORK = {
    "NUM_PROXIES": NUM_PROXIES,
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        # Fail open when the cache is down (core/throttling.py).
        "core.throttling.AnonRateThrottle",
        "core.throttling.UserRateThrottle",
        "core.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="60/min"),
        "user": env("THROTTLE_USER", default="300/min"),
        "auth": env("THROTTLE_AUTH", default="10/min"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ContribFinder API",
    "DESCRIPTION": "Developer-to-contribution-opportunity matching API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    # Issue difficulty and the profile's preferred difficulty share one choice set.
    "ENUM_NAME_OVERRIDES": {
        "DifficultyEnum": "developers.models.IssueDifficulty",
        "DismissReasonEnum": "feedback.models.DismissReason",
    },
}

# --- Celery ----------------------------------------------------------------
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or "cache+memory://"
# Nothing reads task results (jobs record their state in SyncJob), so none are stored.
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = TIME_ZONE
# Keep Django LOGGING (and its secret-redaction filter) in charge of worker logs.
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

# --- Frontend / GitHub OAuth ----------------------------------------------
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173").rstrip("/")
# Fixed post-auth destinations; never taken from request parameters.
FRONTEND_SIGNED_IN_PATH = "/app"
FRONTEND_AUTH_ERROR_PATH = "/"

GITHUB_CLIENT_ID = env("GITHUB_CLIENT_ID", default="")
GITHUB_CLIENT_SECRET = env("GITHUB_CLIENT_SECRET", default="")
# Space- or comma-separated; the authorize URL joins them with spaces.
GITHUB_OAUTH_SCOPES = env_words("GITHUB_OAUTH_SCOPES")
GITHUB_OAUTH_REDIRECT_URI = env(
    "GITHUB_OAUTH_REDIRECT_URI", default=f"{FRONTEND_URL}/api/v1/auth/github/callback"
)
# Pending sign-in states per session (one per tab that started sign-in) and their lifetime.
OAUTH_STATE_MAX_PENDING = env.int("OAUTH_STATE_MAX_PENDING", default=5)
OAUTH_STATE_TTL_SECONDS = env.int("OAUTH_STATE_TTL_SECONDS", default=600)
GITHUB_OAUTH_BASE_URL = "https://github.com"
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_HTTP_TIMEOUT = env.float("GITHUB_HTTP_TIMEOUT", default=10.0)

# --- GitHub sync (Phase 2) ---
GITHUB_SYNC_MAX_REPOS = env.int("GITHUB_SYNC_MAX_REPOS", default=100)
GITHUB_MAX_PAGES = env.int("GITHUB_MAX_PAGES", default=10)
GITHUB_MAX_RETRY_DELAY = env.int("GITHUB_MAX_RETRY_DELAY", default=900)
# Celery broker: a read/write timeout too, so a publish on a stalled connection cannot hang the
# request; unacknowledged messages are redelivered after `visibility_timeout`, kept above the
# longest retry countdown.
CELERY_BROKER_TRANSPORT_OPTIONS: dict[str, float] = {
    "socket_connect_timeout": REDIS_SOCKET_TIMEOUT,
    # Not below 2 s: workers block on BRPOP for 1 s (kombu's brpop_timeout).
    "socket_timeout": max(REDIS_SOCKET_TIMEOUT, 2.0),
    "visibility_timeout": max(3600, 2 * GITHUB_MAX_RETRY_DELAY),
}
GITHUB_ETAG_TTL = env.int("GITHUB_ETAG_TTL", default=24 * 60 * 60)
# After a response-cache error, a process sends GitHub requests unconditionally this long.
GITHUB_CACHE_BACKOFF_SECONDS = env.int("GITHUB_CACHE_BACKOFF_SECONDS", default=30)
SYNC_MAX_ATTEMPTS = env.int("SYNC_MAX_ATTEMPTS", default=5)
SYNC_COOLDOWN_SECONDS = env.int("SYNC_COOLDOWN_SECONDS", default=300)
# A RUNNING job with no heartbeat for this long is treated as dead (worker crash). Jobs beat
# between units of work (a repository, a step), each bounded by HTTP and Redis timeouts.
SYNC_STALE_AFTER_SECONDS = env.int("SYNC_STALE_AFTER_SECONDS", default=10 * 60)
# How often beat requeues RUNNING jobs whose worker died.
JOB_RECOVERY_INTERVAL_SECONDS = env.int("JOB_RECOVERY_INTERVAL_SECONDS", default=5 * 60)

# --- Developer profile (Phase 3) ---
# Evidence strength per source (SRS-1 §15). Configuration, not product rules: an env JSON
# object overrides individual sources, e.g. EVIDENCE_WEIGHTS='{"readme": 0.1}'.
EVIDENCE_WEIGHTS: dict[str, float] = env_mapping(
    "EVIDENCE_WEIGHTS",
    {
        "readme": 0.20,
        "topic": 0.30,
        "language": 0.50,
        "dependency": 0.60,
        "commit": 0.80,
        "pull_request": 0.90,
        "repeated_contribution": 1.00,
    },
)
# Each further piece of evidence from the same source counts `decay` times the previous one.
EVIDENCE_REPEAT_DECAY = env.float("EVIDENCE_REPEAT_DECAY", default=0.5)
CONFIDENCE_CAP = env.float("CONFIDENCE_CAP", default=0.99)
# A repository counts as language evidence when the language is primary or has this share.
LANGUAGE_MIN_SHARE = env.float("LANGUAGE_MIN_SHARE", default=0.10)
REPEATED_CONTRIBUTION_MIN_PRS = env.int("REPEATED_CONTRIBUTION_MIN_PRS", default=3)
INTEREST_EVIDENCE_WEIGHTS: dict[str, float] = env_mapping(
    "INTEREST_EVIDENCE_WEIGHTS",
    {
        "readme": 0.30,
        "repo_description": 0.40,
        "topic": 0.50,
        "contribution": 0.60,
    },
)
INTEREST_MIN_STRENGTH = env.float("INTEREST_MIN_STRENGTH", default=0.35)
# Per signal: [intermediate_from, experienced_from]. Internal matching signal only.
EXPERIENCE_THRESHOLDS: dict[str, list[float]] = env_mapping(
    "EXPERIENCE_THRESHOLDS",
    {
        "account_age_years": [1, 4],
        "active_repositories": [3, 10],
        "merged_external_prs": [1, 15],
        "contributed_repositories": [1, 4],
        "well_evidenced_skills": [3, 8],
    },
)
GITHUB_MANIFEST_MAX_REPOS = env.int("GITHUB_MANIFEST_MAX_REPOS", default=30)
GITHUB_MANIFEST_MAX_BYTES = env.int("GITHUB_MANIFEST_MAX_BYTES", default=512 * 1024)
GITHUB_CONTRIB_MAX_PRS = env.int("GITHUB_CONTRIB_MAX_PRS", default=200)
GITHUB_CONTRIB_MAX_REPOS = env.int("GITHUB_CONTRIB_MAX_REPOS", default=20)

# --- Repository discovery (Phase 4) ---
# Search requests per discovery run (one query in one star band), split across strategies by
# these shares (in this order; unused slots pass to the next strategy).
DISCOVERY_MAX_QUERIES = env.int("DISCOVERY_MAX_QUERIES", default=20)
DISCOVERY_QUERY_SHARES: dict[str, int] = env_mapping(
    "DISCOVERY_QUERY_SHARES",
    {
        "language": 2,
        "skill": 4,
        "interest": 3,
        "topic": 1,
    },
)
DISCOVERY_RESULTS_PER_QUERY = env.int("DISCOVERY_RESULTS_PER_QUERY", default=30)
DISCOVERY_MIN_STARS = env.int("DISCOVERY_MIN_STARS", default=20)

# Every query runs once per star band ([low, high], high null = open-ended), so smaller projects
# are found as well as the most popular ones. The first band starts at DISCOVERY_MIN_STARS.
# Unset (None), the bands follow it: MIN..999 and 1000+, or one open band from MIN when
# MIN >= 1000 (services.discovery.queries.configured_star_bands).
DISCOVERY_STAR_BANDS: list[list[int | None]] | None = env_json("DISCOVERY_STAR_BANDS", None)
# Topics that mark a suspected curated list or documentation repository: `not_code` when it has
# no manifest dependencies, so a library tagged `list` that declares dependencies stays code.
DISCOVERY_EXCLUDED_TOPICS: list[str] = env_json(
    "DISCOVERY_EXCLUDED_TOPICS",
    [
        "awesome",
        "awesome-list",
        "awesome-lists",
        "curated-list",
        "list",
        "lists",
        "books",
        "free-books",
        "interview-questions",
        "cheatsheet",
        "cheatsheets",
    ],
)
DISCOVERY_MAX_PUSH_AGE_DAYS = env.int("DISCOVERY_MAX_PUSH_AGE_DAYS", default=180)
DISCOVERY_MIN_SKILL_CONFIDENCE = env.float("DISCOVERY_MIN_SKILL_CONFIDENCE", default=0.3)
DISCOVERY_MAX_ANALYSES_PER_RUN = env.int("DISCOVERY_MAX_ANALYSES_PER_RUN", default=60)
# Repositories analyzed at once in a discovery run (1 = one after another). Keep it low:
# concurrent requests for one user trip GitHub's secondary rate limits.
DISCOVERY_ANALYSIS_CONCURRENCY = env.int("DISCOVERY_ANALYSIS_CONCURRENCY", default=4)
DISCOVERY_MAX_POOL = env.int("DISCOVERY_MAX_POOL", default=300)
DISCOVERY_CANDIDATE_RETENTION_DAYS = env.int("DISCOVERY_CANDIDATE_RETENTION_DAYS", default=30)

REPO_README_MAX_BYTES = env.int("REPO_README_MAX_BYTES", default=200 * 1024)
REPO_SNAPSHOT_HISTORY = env.int("REPO_SNAPSHOT_HISTORY", default=10)
# Hours after which each data type of a repository is stale (SRS-2 §24).
REPO_STALE_AFTER: dict[str, int] = env_mapping(
    "REPO_STALE_AFTER",
    {
        "issues": 6,
        "metadata": 12,
        "activity": 24,
        "community": 168,
        "dependencies": 168,
        "readme": 168,
    },
)
REPO_REFRESH_BATCH = env.int("REPO_REFRESH_BATCH", default=50)
REPO_DISCOVERED_GRACE_MINUTES = env.int("REPO_DISCOVERED_GRACE_MINUTES", default=10)
REPO_FAILED_RETRY_HOURS = env.int("REPO_FAILED_RETRY_HOURS", default=24)
# Wait after a background refresh failed without a retry (rate-limit wait too long, GitHub
# down for every attempt) before the backlog queues that repository again.
REPO_REFRESH_RETRY_MINUTES = env.int("REPO_REFRESH_RETRY_MINUTES", default=60)

# Activity label thresholds (FR-REPO-004). Observable signals, never a health verdict.
ACTIVITY_THRESHOLDS: dict[str, int] = env_mapping(
    "ACTIVITY_THRESHOLDS",
    {
        "recent_push_days": 30,
        "recent_commits": 10,
        "recent_merged_prs": 5,
        "moderate_push_days": 90,
        "moderate_commits": 1,
        "moderate_merged_prs": 1,
    },
)

# --- Recommendations (Phase 5) ---
# Weights, bands and signal parameters are versioned ScoringConfig rows, not settings.
RECOMMENDATIONS_TOP_N = env.int("RECOMMENDATIONS_TOP_N", default=50)
RECOMMENDATION_MIN_SCORE = env.float("RECOMMENDATION_MIN_SCORE", default=0.10)
# Contributor counts: under "small" is small, under "medium" is medium, otherwise large.
REPO_SIZE_THRESHOLDS: dict[str, int] = env_mapping(
    "REPO_SIZE_THRESHOLDS",
    {
        "small": 10,
        "medium": 100,
    },
)
# The freshness sweep waits this long after a failed generation before starting another.
RECOMMENDATION_FAILED_RETRY_MINUTES = env.int("RECOMMENDATION_FAILED_RETRY_MINUTES", default=360)
RECOMMENDATION_REFRESH_INTERVAL_SECONDS = env.int(
    "RECOMMENDATION_REFRESH_INTERVAL_SECONDS", default=30 * 60
)
RECOMMENDATION_README_EXCERPT_CHARS = env.int("RECOMMENDATION_README_EXCERPT_CHARS", default=1500)

# --- Feedback (Phase 8a) ---
# A second "viewed" event for the same recommendation within this window is not recorded.
FEEDBACK_VIEW_DEDUP_MINUTES = env.int("FEEDBACK_VIEW_DEDUP_MINUTES", default=30)

# --- Issues (Phase 7) ---
# Issue matching weights, thresholds and the difficulty fit table are ScoringConfig params.
ISSUES_MAX_PAGES = env.int("ISSUES_MAX_PAGES", default=1)
# Entry labels (GitHub's default names): one page of open issues per label is fetched besides
# the most recent ones, so older entry issues of big repositories are not cut off. Empty: none.
ISSUES_ENTRY_LABELS = env_list("ISSUES_ENTRY_LABELS", default=["good first issue", "help wanted"])
ISSUE_BODY_MAX_CHARS = env.int("ISSUE_BODY_MAX_CHARS", default=10_000)
ISSUE_MAX_AGE_DAYS = env.int("ISSUE_MAX_AGE_DAYS", default=365)
# Difficulty votes: a body under short_body votes beginner, over long_body advanced; one
# technology votes beginner, several_technologies or more intermediate, many_technologies or
# more advanced; long_discussion comments or more vote advanced. A level needs min_votes
# agreeing votes (at least 2) and no vote for another level.
ISSUE_DIFFICULTY: dict[str, int] = env_mapping(
    "ISSUE_DIFFICULTY",
    {
        "short_body": 600,
        "long_body": 4000,
        "several_technologies": 2,
        "many_technologies": 3,
        "long_discussion": 15,
        "min_votes": 2,
    },
)

CELERY_BEAT_SCHEDULE = {
    "recover-stale-jobs": {
        "task": "jobs.recover_stale_jobs",
        "schedule": float(JOB_RECOVERY_INTERVAL_SECONDS),
    },
    "mark-stale-repositories": {
        "task": "repositories.mark_stale_repositories",
        "schedule": 60 * 60.0,
    },
    "process-repository-backlog": {
        "task": "repositories.process_repository_backlog",
        "schedule": 15 * 60.0,
    },
    "refresh-recommendations": {
        "task": "recommendations.refresh_recommendations",
        "schedule": float(RECOMMENDATION_REFRESH_INTERVAL_SECONDS),
    },
}

# Comma-separated Fernet keys, newest first.
TOKEN_ENCRYPTION_KEYS = env_list("TOKEN_ENCRYPTION_KEYS", default=[])

# --- Logging ---------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact_secrets": {"()": "core.logging.RedactSecretsFilter"}},
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["redact_secrets"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # Replace Django's default "django" handler (it has no redaction filter) so every
        # Django log line goes through the filtered console handler exactly once.
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # Never SQL with its parameters (session keys, tokens), whatever LOG_LEVEL says.
        "django.db.backends": {"level": "INFO"},
        # Keep request bodies/URLs of the httpx client out of INFO logs.
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    },
}
