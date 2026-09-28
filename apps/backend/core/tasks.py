from celery import shared_task


@shared_task(name="core.ping")
def ping() -> str:
    """Liveness probe for the Celery worker."""
    return "pong"
