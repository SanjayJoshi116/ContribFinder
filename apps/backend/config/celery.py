import os
from typing import Any

from celery import Celery
from celery.signals import beat_init, worker_init

# Same default as wsgi.py, so web and workers never differ by accident; the local runners and
# compose set development explicitly.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("contribfinder")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_init.connect
@beat_init.connect
def _check_configuration(**kwargs: Any) -> None:
    from core.startup import run_startup_checks

    run_startup_checks()
