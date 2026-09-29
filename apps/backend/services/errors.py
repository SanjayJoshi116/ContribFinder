"""Errors shared by background job services."""


class PermanentJobError(Exception):
    """A failure that retrying cannot fix. ``code`` becomes the job's ``error_code``."""

    code = "internal_error"
