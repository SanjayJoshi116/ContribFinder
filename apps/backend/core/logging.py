"""Backstop that keeps credentials out of log output.

Primary protection is never logging secrets in the first place; this filter masks
anything that slips through (query-string, JSON and GitHub token formats).
"""

import logging
import re

_REDACTED = "[REDACTED]"

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # key=value (query strings, form bodies, reprs)
    (
        re.compile(r"(?i)\b(access_token|refresh_token|client_secret|code|state)=([^&\s'\",]+)"),
        rf"\1={_REDACTED}",
    ),
    # "key": "value" (JSON / dict reprs)
    (
        re.compile(
            r"(?i)(['\"](?:access_token|refresh_token|client_secret|code)['\"]\s*:\s*)"
            r"(['\"])[^'\"]*\2"
        ),
        rf"\1\2{_REDACTED}\2",
    ),
    # Authorization header values (Bearer tokens, Basic client credentials)
    (re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9+/=._-]{8,}"), rf"\1 {_REDACTED}"),
    # GitHub token formats: gho_, ghu_, ghp_, ghs_, ghr_, github_pat_
    (re.compile(r"\b(gh[opusr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,})\b"), _REDACTED),
)


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True
