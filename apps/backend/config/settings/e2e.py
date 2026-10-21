"""Browser (Playwright) tests against a real server: `npm run e2e` in apps/frontend.

Self-contained on purpose: `scripts/e2e-backend.mjs` passes only `DATABASE_URL` from a local
`.env` (the server to reach; the database name is set here) and turns `.env` reading off, so
local runs see CI's settings; Redis is off, and GitHub is unreachable, so a test that would
call it fails at once. Only this
module installs the `e2e` app, whose seed command is the one way in without GitHub; no other
settings module, production included, has it.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "e2e-secret-key-not-for-production")
os.environ.setdefault("TOKEN_ENCRYPTION_KEYS", "a3xvsSaVgXP5fzzK-ehE3KBhB0NR2UBdgAPViFYjPW8=")

from .base import *  # noqa: F403
from .base import DATABASES, INSTALLED_APPS

DEBUG = False

INSTALLED_APPS = [*INSTALLED_APPS, "e2e"]

# A copy: the dict is base's object, shared with any other settings module imported here.
DATABASES = {"default": {**DATABASES["default"], "NAME": "contribfinder_e2e", "CONN_MAX_AGE": 0}}

# No Redis: in-process cache, tasks run inline in the request that queues them.
REDIS_URL = ""
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True
RUN_STARTUP_CHECKS = False

# Nothing listens on port 9 (discard): any GitHub call fails immediately.
GITHUB_OAUTH_BASE_URL = "http://127.0.0.1:9"
GITHUB_API_BASE_URL = "http://127.0.0.1:9"
GITHUB_HTTP_TIMEOUT = 2.0
GITHUB_CLIENT_ID = "e2e-client-id"
GITHUB_CLIENT_SECRET = "e2e-client-secret"  # noqa: S105

# The Vite server the tests drive (apps/frontend/playwright.config.ts).
FRONTEND_URL = "http://localhost:5174"
GITHUB_OAUTH_REDIRECT_URI = f"{FRONTEND_URL}/api/v1/auth/github/callback"
