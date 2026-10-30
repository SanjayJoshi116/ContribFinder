"""Backstop that keeps credentials out of log output.

Primary protection is never logging secrets in the first place; this filter masks
anything that slips through (query-string, quoted key=value, JSON/dict, Authorization
header and GitHub token formats). It never raises into the code that logs.
"""

import logging
import re

_REDACTED = "[REDACTED]"
_KEYS = (
    r"access_token|refresh_token|client_secret|code|state|secret|password|sessionid|csrftoken"
    r"|encryption_keys"
)
# A key also matches at the end of a longer name: GITHUB_CLIENT_SECRET=, encrypted_access_token=.
_NAME = rf"\b(\w*?(?:{_KEYS}))"

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # key='value' / key="value" (reprs, keyword arguments)
    (re.compile(rf"(?i){_NAME}=(['\"])[^'\"]*\2"), rf"\1=\2{_REDACTED}\2"),
    # key=value (query strings, form bodies, cookies)
    (re.compile(rf"(?i){_NAME}=([^&;\s'\",]+)"), rf"\1={_REDACTED}"),
    # "key": "value" (JSON / dict reprs)
    (
        re.compile(rf"(?i)(['\"]\w*?(?:{_KEYS}|authorization)['\"]\s*:\s*)(['\"])[^'\"]*\2"),
        rf"\1\2{_REDACTED}\2",
    ),
    # Authorization header, whatever the scheme (token, Bearer, Basic) or value format
    (
        re.compile(r"(?i)\b(Authorization\s*:\s*)([A-Za-z]+\s+)?[^\s'\",]+"),
        rf"\1\2{_REDACTED}",
    ),
    # Bearer/Basic values without the header name
    (re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9+/=._-]{8,}"), rf"\1 {_REDACTED}"),
    # GitHub token formats: gho_, ghu_, ghp_, ghs_, ghr_, github_pat_
    (re.compile(r"\b(gh[opusr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,})\b"), _REDACTED),
)


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _message(record: logging.LogRecord) -> str:
    try:
        return record.getMessage()
    except Exception:
        # A bad log call (wrong argument count, failing __str__) must not crash the caller.
        try:
            return f"{record.msg} (unformatted args: {record.args!r})"
        except Exception:
            return "<unprintable log message>"


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(_message(record))
        record.args = ()
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True
