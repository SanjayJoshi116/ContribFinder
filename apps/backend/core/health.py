import functools
import logging

import redis
from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

OK = "ok"
UNAVAILABLE = "unavailable"
# Local development without Redis (in-process cache, eager Celery). Production requires Redis.
NOT_CONFIGURED = "not_configured"
HEALTHY = frozenset({OK, NOT_CONFIGURED})


def check_database() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.warning("Health check: database unavailable")
        return UNAVAILABLE
    return OK


@functools.cache
def _redis_client(url: str) -> redis.Redis:
    """One client (and connection pool) per process: probes reuse it, and it reconnects by
    itself after an outage."""
    return redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def check_redis() -> str:
    if not settings.REDIS_URL:
        return NOT_CONFIGURED
    try:
        _redis_client(settings.REDIS_URL).ping()
    except Exception:
        logger.warning("Health check: redis unavailable")
        return UNAVAILABLE
    return OK


def run_checks() -> dict[str, str]:
    return {"database": check_database(), "redis": check_redis()}
