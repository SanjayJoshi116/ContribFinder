"""Errors shared by background job services, and how a final failure is logged."""

from __future__ import annotations

import logging
from typing import Any

INTERNAL_ERROR = "internal_error"


class PermanentJobError(Exception):
    """A failure that retrying cannot fix. ``code`` becomes the job's ``error_code``."""

    code = INTERNAL_ERROR


class JobCancelled(Exception):
    """The job was cancelled (e.g. GitHub disconnected); stop without further requests."""


def log_failure(
    logger: logging.Logger,
    code: str,
    exc: BaseException,
    message: str,
    *args: Any,
    expected: tuple[type[BaseException], ...] = (),
) -> None:
    """Log a final failure (no retry left) as ``message: code``, with ``code`` from
    ``decide_retry``. An unexpected one (``internal_error``, and ``exc`` not one of
    ``expected``) is a bug: ERROR with its traceback. Anything else (GitHub refused, a typed job
    error) is WARNING with the exception type only, never its text."""
    if code == INTERNAL_ERROR and not isinstance(exc, expected):
        logger.error(message + ": %s", *args, code, exc_info=exc)
    else:
        logger.warning(message + ": %s (%s)", *args, code, type(exc).__name__)
