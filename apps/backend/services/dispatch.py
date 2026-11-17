"""Sending Celery tasks (change task-dispatch-and-failure-logs).

A broker that refuses a task (``kombu`` ``OperationalError``) never fails work that is already
done: the refusal is logged and whatever keeps state for the task (job recovery for a PENDING
job) sends it again later. Any other error propagates, so a bug is never hidden. Records name
the task and ``about``, never the arguments (a revocation carries a token, if encrypted).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from kombu.exceptions import OperationalError as BrokerError

logger = logging.getLogger(__name__)

__all__ = ["after_commit", "send"]


def send(task: Any, *args: Any, about: str = "", **options: Any) -> bool:
    """Send ``task(*args)`` now (``apply_async`` with ``options`` such as ``countdown``, else
    ``delay``). Returns whether the broker took it; a refusal is logged with its traceback."""
    try:
        if options:
            task.apply_async(args, **options)
        else:
            task.delay(*args)
    except BrokerError:
        logger.warning(
            "Task %s not queued%s", task.name, f" ({about})" if about else "", exc_info=True
        )
        return False
    return True


def after_commit(
    task: Any, *args: Any, about: str = "", robust: bool = False, **options: Any
) -> None:
    """``send`` once the current transaction commits (at once outside one); nothing on
    rollback. ``robust`` also logs any other send error instead of raising it, for a caller
    whose committed work must not fail with a 500 nor skip later on-commit callbacks."""
    transaction.on_commit(lambda: send(task, *args, about=about, **options), robust=robust)
