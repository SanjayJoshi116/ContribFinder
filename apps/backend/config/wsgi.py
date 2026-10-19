import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()

from core.startup import run_startup_checks  # noqa: E402  (needs configured apps)

run_startup_checks()
