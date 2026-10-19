from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import NUM_PROXIES, env

# The in-process cache / eager-Celery fallback is for local development only.
if not env("REDIS_URL", default=""):
    raise ImproperlyConfigured("REDIS_URL must be set in production.")

DEBUG = False

# Web server and workers refuse to start on system check errors (core.startup).
RUN_STARTUP_CHECKS = True

# X-Forwarded-Proto is trusted only when a proxy we control sets it (NUM_PROXIES).
if NUM_PROXIES > 0:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
# Load-balancer probes may use plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
# Both affect other hosts on the domain (preload is near-irreversible once submitted): opt-in.
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
