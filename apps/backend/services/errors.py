"""Errors shared by background job services."""


class PermanentJobError(Exception):
    """A failure that retrying cannot fix. ``code`` becomes the job's ``error_code``."""

    code = "internal_error"


class JobCancelled(Exception):
    """The job was cancelled (e.g. GitHub disconnected); stop without further requests."""
