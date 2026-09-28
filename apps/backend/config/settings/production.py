from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env

# The in-process cache / eager-Celery fallback is for local development only.
if not env("REDIS_URL", default=""):
    raise ImproperlyConfigured("REDIS_URL must be set in production.")

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
