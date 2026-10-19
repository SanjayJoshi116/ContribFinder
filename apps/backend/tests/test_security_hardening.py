"""Trusted proxies, health probes and production defaults (change security-hardening)."""

import runpy
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client, RequestFactory
from rest_framework.test import APIClient

from accounts.models import AuditEvent
from core.checks import trusted_proxy_check
from services import audit
from services.audit import client_ip

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("tests.urls"),
    # _production() re-executes the settings module on purpose.
    pytest.mark.filterwarnings("ignore:'config.settings.production' found in sys.modules"),
]

THROTTLED = "/api/v1/_test/throttled/"  # 1/min per anonymous client
HEALTH = "/api/v1/health/"


def _production(
    monkeypatch: pytest.MonkeyPatch, num_proxies: int = 0, **env: str
) -> dict[str, Any]:
    """Evaluate config.settings.production with the given environment and NUM_PROXIES."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("config.settings.base.NUM_PROXIES", num_proxies)
    return runpy.run_module("config.settings.production")


def _trust_proxies(settings: Any, count: int) -> None:
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": count}


# --- Client identity -------------------------------------------------------


def test_forwarded_for_is_ignored_without_trusted_proxies(api_client: APIClient, settings) -> None:
    _trust_proxies(settings, 0)
    assert api_client.get(THROTTLED, HTTP_X_FORWARDED_FOR="198.51.100.1").status_code == 200
    response = api_client.get(THROTTLED, HTTP_X_FORWARDED_FOR="198.51.100.2")
    assert response.status_code == 429


def test_trusted_proxy_address_is_used_and_prepended_values_ignored(
    api_client: APIClient, settings
) -> None:
    _trust_proxies(settings, 1)
    first = api_client.get(THROTTLED, HTTP_X_FORWARDED_FOR="spoof-1, 203.0.113.7")
    assert first.status_code == 200
    # Same real client behind the proxy, different spoofed prefix: still throttled.
    again = api_client.get(THROTTLED, HTTP_X_FORWARDED_FOR="spoof-2, 203.0.113.7")
    assert again.status_code == 429
    # A different real client has its own bucket.
    other = api_client.get(THROTTLED, HTTP_X_FORWARDED_FOR="spoof-1, 203.0.113.8")
    assert other.status_code == 200


@pytest.mark.parametrize(
    ("proxies", "xff", "expected"),
    [
        (0, None, "10.0.0.1"),
        (0, "203.0.113.7", "10.0.0.1"),
        (1, None, "10.0.0.1"),
        (1, "spoof, 203.0.113.7", "203.0.113.7"),
        (2, "spoof, 203.0.113.7, 10.1.1.1", "203.0.113.7"),
        (3, "203.0.113.7", "203.0.113.7"),
    ],
)
def test_client_ip(settings, proxies: int, xff: str | None, expected: str) -> None:
    _trust_proxies(settings, proxies)
    headers = {"X-Forwarded-For": xff} if xff else {}
    request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", headers=headers)
    assert client_ip(request) == expected


def test_audit_ip_hash_follows_trusted_proxy_rule(settings, user) -> None:
    _trust_proxies(settings, 1)
    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="spoof, 203.0.113.7"
    )
    event = audit.record(AuditEvent.Action.LOGOUT, AuditEvent.Outcome.SUCCESS, request=request)
    assert event.ip_hash == audit.hash_ip("203.0.113.7")


def test_forwarded_proto_is_trusted_only_with_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "SECURE_PROXY_SSL_HEADER" not in _production(monkeypatch, num_proxies=0)
    assert _production(monkeypatch, num_proxies=1)["SECURE_PROXY_SSL_HEADER"] == (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )


def test_untrusted_forwarded_proto_is_not_secure(api_client: APIClient, settings) -> None:
    settings.SECURE_SSL_REDIRECT = True
    response = api_client.get("/api/v1/_test/protected/", HTTP_X_FORWARDED_PROTO="https")
    assert response.status_code == 301


def test_ssl_redirect_without_trusted_proxies_warns(settings) -> None:
    settings.SECURE_SSL_REDIRECT = True
    settings.NUM_PROXIES = 0
    assert [m.id for m in trusted_proxy_check()] == ["core.W002"]
    settings.NUM_PROXIES = 1
    assert trusted_proxy_check() == []
    settings.SECURE_SSL_REDIRECT = False
    settings.NUM_PROXIES = 0
    assert trusted_proxy_check() == []


# --- Health check ----------------------------------------------------------


def test_health_is_not_throttled(api_client: APIClient, settings) -> None:
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "anon": "2/min",
        },
    }
    with patch("core.health.check_redis", return_value="ok"):
        statuses = {api_client.get(HEALTH).status_code for _ in range(5)}
    assert statuses == {200}


def test_plain_http_health_probe_is_not_redirected(
    api_client: APIClient, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = _production(monkeypatch)["SECURE_REDIRECT_EXEMPT"]
    with patch("core.health.check_redis", return_value="ok"):
        assert api_client.get(HEALTH).status_code == 200
    assert api_client.get("/api/v1/_test/protected/").status_code == 301


# --- Framework-level errors ------------------------------------------------


def test_disallowed_host_uses_error_envelope(settings) -> None:
    settings.ALLOWED_HOSTS = ["testserver"]
    response = Client().get(HEALTH, HTTP_HOST="evil.example")
    assert response.status_code == 400
    assert response.json() == {"error": {"code": "bad_request", "message": "Bad request."}}


def test_permission_denied_outside_drf_uses_error_envelope() -> None:
    response = Client().get("/api/v1/_test/denied/")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


# --- HSTS ------------------------------------------------------------------


def test_hsts_subdomains_and_preload_are_opt_in(
    api_client: APIClient, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    production = _production(monkeypatch)
    assert production["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is False
    assert production["SECURE_HSTS_PRELOAD"] is False
    settings.SECURE_HSTS_SECONDS = 3600
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = production["SECURE_HSTS_INCLUDE_SUBDOMAINS"]
    settings.SECURE_HSTS_PRELOAD = production["SECURE_HSTS_PRELOAD"]
    with patch("core.health.check_redis", return_value="ok"):
        response = api_client.get(HEALTH, secure=True)
    assert response.headers["Strict-Transport-Security"] == "max-age=3600"


def test_hsts_directives_can_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    production = _production(
        monkeypatch, SECURE_HSTS_INCLUDE_SUBDOMAINS="true", SECURE_HSTS_PRELOAD="true"
    )
    assert production["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is True
    assert production["SECURE_HSTS_PRELOAD"] is True
    assert production["RUN_STARTUP_CHECKS"] is True
