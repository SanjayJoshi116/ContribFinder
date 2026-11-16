"""Content-Security-Policy on backend responses (change content-security-policy)."""

import re
from unittest.mock import patch

import pytest
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import Client, override_settings
from rest_framework.test import APIClient

from core.checks import content_security_policy_check
from core.csp import HEADER, ContentSecurityPolicyMiddleware, is_json

from .checks_helpers import ids

API_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

pytestmark = pytest.mark.django_db


def test_api_response_gets_the_deny_all_policy(api_client: APIClient) -> None:
    with patch("core.health.check_redis", return_value="ok"):
        response = api_client.get("/api/v1/health/")
    assert response.headers[HEADER] == API_POLICY


@pytest.mark.parametrize("path", ["/api/v1/auth/me", "/api/v1/no-such-endpoint"])
def test_api_errors_get_the_deny_all_policy(api_client: APIClient, path: str) -> None:
    response = api_client.get(path)
    assert response.status_code in (401, 404)
    assert response.headers[HEADER] == API_POLICY


def test_admin_page_gets_the_html_policy(admin_client: Client) -> None:
    response = admin_client.get("/admin/")
    assert response.status_code == 200
    policy = response.headers[HEADER]
    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "object-src 'none'" in policy
    # The admin runs under the policy: every script it includes is a file, none inline.
    scripts = re.findall(r"<script\b[^>]*>", response.content.decode(), re.IGNORECASE)
    assert scripts
    assert all("src=" in tag or 'type="application/json"' in tag for tag in scripts)


def test_a_views_own_policy_is_kept() -> None:
    def view(request: HttpRequest) -> HttpResponse:
        response = HttpResponse("ok")
        response[HEADER] = "default-src 'self' https://example.com"
        return response

    response = ContentSecurityPolicyMiddleware(view)(HttpRequest())
    assert response[HEADER] == "default-src 'self' https://example.com"


def test_policy_follows_the_media_type() -> None:
    json = ContentSecurityPolicyMiddleware(lambda request: JsonResponse({}))(HttpRequest())
    html = ContentSecurityPolicyMiddleware(lambda request: HttpResponse("<p>"))(HttpRequest())
    assert json[HEADER] == API_POLICY
    assert "default-src 'self'" in html[HEADER]


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("application/json", True),
        ("application/json; charset=utf-8", True),
        ("application/problem+json", True),
        ("Application/JSON", True),
        ("text/html; charset=utf-8", False),
        ("", False),
    ],
)
def test_is_json(content_type: str, expected: bool) -> None:
    assert is_json(content_type) is expected


@pytest.mark.parametrize("value", ["", "   ", None])
@pytest.mark.parametrize("name", ["CONTENT_SECURITY_POLICY_API", "CONTENT_SECURITY_POLICY_HTML"])
def test_empty_policy_is_refused(name: str, value: object) -> None:
    with override_settings(**{name: value}):
        errors = content_security_policy_check()
    assert ids(errors) == ["core.E060"]
    assert name in errors[0].msg


def test_default_policies_pass_the_check() -> None:
    assert content_security_policy_check() == []
