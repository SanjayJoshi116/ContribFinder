import os

# Deterministic, non-secret values so the suite runs without a .env.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
# DATABASE_URL: CI sets it; locally base.py defaults to the local PostgreSQL install.
os.environ.setdefault("TOKEN_ENCRYPTION_KEYS", "a3xvsSaVgXP5fzzK-ehE3KBhB0NR2UBdgAPViFYjPW8=")

from .base import *  # noqa: F403

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

GITHUB_CLIENT_ID = "test-client-id"
GITHUB_CLIENT_SECRET = "test-client-secret"  # noqa: S105
FRONTEND_URL = "http://testserver-frontend"
GITHUB_OAUTH_REDIRECT_URI = "http://testserver/api/v1/auth/github/callback"
CORS_ALLOWED_ORIGINS = ["http://allowed.example"]
CSRF_TRUSTED_ORIGINS = ["http://allowed.example"]
