"""Refuse to serve or run jobs with invalid configuration (production web server and workers).

Django runs system checks only for management commands; gunicorn and Celery never do. The WSGI
module and Celery's worker/beat init signals call `run_startup_checks()`, which is active when
`RUN_STARTUP_CHECKS` is set (production settings).
"""

import logging

from django.conf import settings
from django.core import checks
from django.core.management.base import SystemCheckError

logger = logging.getLogger(__name__)


def run_startup_checks() -> None:
    if not settings.RUN_STARTUP_CHECKS:
        return
    errors = []
    for message in checks.run_checks():
        if message.is_serious():
            errors.append(str(message))
        elif not message.is_silenced():
            logger.warning("System check %s", message)
    if errors:
        raise SystemCheckError("Configuration errors, refusing to start:\n" + "\n".join(errors))
