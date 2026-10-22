from unittest.mock import patch

import pytest
from django.test import Client
from rest_framework.test import APIClient

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.urls")]


def test_path_without_version_prefix_is_404(api_client: APIClient) -> None:
    assert api_client.get("/health/").status_code == 404


def test_unknown_api_path_uses_error_envelope(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/does-not-exist/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_validation_error_envelope(api_client: APIClient) -> None:
    response = api_client.post("/api/v1/_test/validate/", {"name": "toolong"}, format="json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"]
    assert "name" in error["details"]


def test_unauthenticated_is_401(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/_test/protected/")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_post_without_csrf_is_rejected(csrf_client: APIClient, user) -> None:
    csrf_client.force_login(user)
    response = csrf_client.post("/api/v1/_test/protected/")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_post_with_csrf_token_succeeds(user) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get("/api/v1/auth/csrf/")
    token = client.cookies["csrftoken"].value
    response = client.post("/api/v1/_test/protected/", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200


def test_throttled_envelope_and_retry_after(api_client: APIClient) -> None:
    assert api_client.get("/api/v1/_test/throttled/").status_code == 200
    response = api_client.get("/api/v1/_test/throttled/")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"
    assert "Retry-After" in response.headers


def test_unhandled_error_hides_internals(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/_test/boom/")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "server_error"
    assert "secret internal detail" not in response.content.decode()
    assert "Traceback" not in response.content.decode()


def test_health_ok(api_client: APIClient) -> None:
    with patch("core.health.check_redis", return_value="ok"):
        response = api_client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


def test_health_ok_without_redis_configured(api_client: APIClient, settings) -> None:
    settings.REDIS_URL = ""
    response = api_client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "not_configured"}


def test_health_degraded_when_redis_down(api_client: APIClient, settings) -> None:
    settings.REDIS_URL = "redis://:pw@host:6379/0"
    with patch("core.health.redis.Redis.from_url") as from_url:
        from_url.return_value.ping.side_effect = ConnectionError("redis://:pw@host")
        response = api_client.get("/api/v1/health/")
    assert response.status_code == 503
    body = response.json()
    assert body["checks"] == {"database": "ok", "redis": "unavailable"}
    assert "redis://" not in response.content.decode()


def test_health_reuses_one_redis_client(api_client: APIClient, settings) -> None:
    settings.REDIS_URL = "redis://localhost:6379/9"
    with patch("core.health.redis.Redis.from_url") as from_url:
        api_client.get("/api/v1/health/")
        api_client.get("/api/v1/health/")
    assert from_url.call_count == 1
    assert from_url.return_value.ping.call_count == 2


def test_health_degraded_when_database_down(api_client: APIClient) -> None:
    with (
        patch("core.health.check_redis", return_value="ok"),
        patch("core.health.connection.cursor", side_effect=Exception("db down")),
    ):
        response = api_client.get("/api/v1/health/")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unavailable"


def test_security_headers_present(api_client: APIClient) -> None:
    with patch("core.health.check_redis", return_value="ok"):
        response = api_client.get("/api/v1/health/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"


def test_cors_allows_configured_origin(api_client: APIClient) -> None:
    with patch("core.health.check_redis", return_value="ok"):
        response = api_client.get("/api/v1/health/", HTTP_ORIGIN="http://allowed.example")
    assert response.headers["Access-Control-Allow-Origin"] == "http://allowed.example"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


def test_cors_rejects_unknown_origin(api_client: APIClient) -> None:
    with patch("core.health.check_redis", return_value="ok"):
        response = api_client.get("/api/v1/health/", HTTP_ORIGIN="http://evil.example")
    assert "Access-Control-Allow-Origin" not in response.headers


def test_schema_is_openapi_3(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/health/" in schema["paths"]
