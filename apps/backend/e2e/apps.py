from django.apps import AppConfig


class E2EConfig(AppConfig):
    """Browser-test seeding. Installed only by ``config.settings.e2e``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "e2e"
