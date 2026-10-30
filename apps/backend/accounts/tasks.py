from importlib import import_module

from celery import shared_task
from django.conf import settings


@shared_task(name="accounts.clear_expired_sessions")
def clear_expired_sessions() -> None:
    """Delete expired sessions (every anonymous sign-in start stores one); the configured
    engine's own cleanup, as `manage.py clearsessions` runs it."""
    import_module(settings.SESSION_ENGINE).SessionStore.clear_expired()
