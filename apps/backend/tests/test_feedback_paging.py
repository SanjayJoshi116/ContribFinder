"""Keyset paging of the saved and hidden lists (spec recommendation-feedback, "Complete saved
and hidden lists"; design D2 of freshness-paging-seed)."""

import base64
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from e2e.builders import make_candidate_repo
from feedback.models import DismissedRepository, SavedRepository

from .factories import UserFactory

pytestmark = pytest.mark.django_db

LISTS = [
    pytest.param("/api/v1/saved", SavedRepository, "saved_at", id="saved"),
    pytest.param("/api/v1/dismissed", DismissedRepository, "dismissed_at", id="dismissed"),
]
BASE = timezone.now() - timedelta(days=1)


def add(user, model, time_field: str, n: int, *, start: int = 0, at=None) -> list[int]:
    """``n`` entries, entry i one minute after entry i-1 (or all at ``at``); repository ids."""
    ids = []
    for i in range(start, start + n):
        repo = make_candidate_repo(1000 + i)
        entry = model.objects.create(user=user, repository=repo)
        model.objects.filter(pk=entry.pk).update(**{time_field: at or BASE + timedelta(minutes=i)})
        ids.append(repo.pk)
    return ids


def repo_ids(body: dict[str, Any]) -> list[int]:
    return [entry["repository_id"] for entry in body["results"]]


def follow(client: APIClient, url: str) -> dict[str, Any]:
    response = client.get(url)
    assert response.status_code == 200, response.json()
    body: dict[str, Any] = response.json()
    return body


def next_path(body: dict[str, Any]) -> str:
    parts = urlsplit(body["next"])
    return f"{parts.path}?{parts.query}"


@pytest.mark.parametrize(("path", "model", "time_field"), LISTS)
def test_following_next_lists_every_entry_once_newest_first(
    signed_in_client, user, path, model, time_field
) -> None:
    ids = add(user, model, time_field, 60)
    first = follow(signed_in_client, f"{path}?page_size=50")
    assert first["count"] == 60
    assert "cursor" in parse_qs(urlsplit(first["next"]).query)
    assert "page" not in parse_qs(urlsplit(first["next"]).query)
    second = follow(signed_in_client, next_path(first))

    assert (second["count"], second["next"], second["previous"]) == (60, None, None)
    assert repo_ids(first) + repo_ids(second) == ids[::-1]


@pytest.mark.parametrize(("path", "model", "time_field"), LISTS)
def test_removal_between_pages_neither_repeats_nor_skips(
    signed_in_client, user, path, model, time_field
) -> None:
    ids = add(user, model, time_field, 60)
    first = follow(signed_in_client, f"{path}?page_size=50")
    model.objects.filter(user=user, repository_id=repo_ids(first)[3]).delete()

    second = follow(signed_in_client, next_path(first))

    assert repo_ids(second) == ids[:10][::-1]
    assert second["count"] == 59


@pytest.mark.parametrize(("path", "model", "time_field"), LISTS)
def test_addition_between_pages_does_not_repeat(
    signed_in_client, user, path, model, time_field
) -> None:
    ids = add(user, model, time_field, 60)
    first = follow(signed_in_client, f"{path}?page_size=50")
    add(user, model, time_field, 1, start=60)  # newest: belongs before page 1

    second = follow(signed_in_client, next_path(first))

    assert repo_ids(second) == ids[:10][::-1]


@pytest.mark.parametrize(("path", "model", "time_field"), LISTS)
def test_equal_times_page_by_id(signed_in_client, user, path, model, time_field) -> None:
    ids = add(user, model, time_field, 5, at=BASE)
    first = follow(signed_in_client, f"{path}?page_size=2")
    second = follow(signed_in_client, next_path(first))
    third = follow(signed_in_client, next_path(second))

    listed = repo_ids(first) + repo_ids(second) + repo_ids(third)
    assert sorted(listed) == sorted(ids) and len(listed) == 5
    assert third["next"] is None


@pytest.mark.parametrize(("path", "model", "time_field"), LISTS)
def test_page_numbers_still_work_without_a_cursor(
    signed_in_client, user, path, model, time_field
) -> None:
    ids = add(user, model, time_field, 25)
    body = follow(signed_in_client, f"{path}?page=2&page_size=10")

    assert body["count"] == 25
    assert repo_ids(body) == ids[::-1][10:20]
    assert body["previous"] is not None
    third = follow(signed_in_client, next_path(body))  # the cursor continues after page 2
    assert repo_ids(third) == ids[::-1][20:]


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


@pytest.mark.parametrize(("path", "model", "time_field"), LISTS)
@pytest.mark.parametrize(
    "cursor",
    [
        "garbage!",
        encoded("not-a-time|5"),
        encoded("2026-10-22T10:00:00+00:00|abc"),
        encoded("2026-10-22T10:00:00|5"),  # no time zone
        encoded("2026-10-22T10:00:00+00:00"),
    ],
)
def test_unreadable_cursor_is_rejected(
    signed_in_client, user, path, model, time_field, cursor
) -> None:
    response = signed_in_client.get(f"{path}?cursor={cursor}")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


@pytest.mark.parametrize(("path", "model", "time_field"), LISTS)
def test_other_users_entries_never_appear(signed_in_client, user, path, model, time_field) -> None:
    mine = add(user, model, time_field, 3)
    add(UserFactory(), model, time_field, 3, start=10)
    first = follow(signed_in_client, f"{path}?page_size=2")
    second = follow(signed_in_client, next_path(first))

    assert repo_ids(first) + repo_ids(second) == mine[::-1]
    assert (first["count"], second["count"]) == (3, 3)
