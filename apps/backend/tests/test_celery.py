from core.tasks import ping


def test_ping_task_runs() -> None:
    assert ping.delay().get(timeout=5) == "pong"


def test_task_results_are_not_stored() -> None:
    """Nothing reads them; storing every result in Redis only costs memory (H-20)."""
    from config.celery import app

    assert app.conf.task_ignore_result is True
