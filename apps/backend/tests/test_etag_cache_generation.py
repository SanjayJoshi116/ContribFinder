"""User-scope ETag entries never outlive a GitHub data deletion (SVC-16, change
etag-cache-generation)."""

import logging
from unittest.mock import patch

import pytest
import respx
from celery.exceptions import Retry as CeleryRetry
from django.core.cache import cache
from django.db import DatabaseError
from django.test import override_settings

from accounts.models import User
from github.tasks import PURGE_ATTEMPTS, purge_user_cache
from services import data_deletion
from services.github.client import PUBLIC_SCOPE, GitHubClient

pytestmark = pytest.mark.django_db

API = "https://api.github.com"


def user_keys(user: User) -> list[str]:
    return [k for k in cache._cache if f"github:etag:{user.pk}:" in k]  # type: ignore[attr-defined]


def languages() -> None:
    """Serve ``o/r`` languages with an ETag, so the client caches the response."""
    respx.get(f"{API}/repos/o/r/languages").respond(200, json={"Go": 5}, headers={"ETag": '"e"'})


@respx.mock
def test_entry_written_by_a_current_client_is_kept(user: User) -> None:
    languages()
    with GitHubClient.for_user(user) as client:
        client.get_languages("o/r")
    assert len(user_keys(user)) == 1


@respx.mock
def test_entry_written_after_a_deletion_committed_is_removed(
    user: User, django_capture_on_commit_callbacks
) -> None:
    languages()
    with GitHubClient.for_user(user) as client:  # built before the deletion
        with django_capture_on_commit_callbacks(execute=True):
            data_deletion.delete_github_data(user)
        assert client.get_languages("o/r") == {"Go": 5}  # served, not kept
    assert user_keys(user) == []


@respx.mock
def test_entry_written_after_account_deletion_is_removed(user: User) -> None:
    languages()
    with GitHubClient.for_user(user) as client:
        User.objects.filter(pk=user.pk).delete()
        client.get_languages("o/r")
    assert user_keys(user) == []  # ``user`` keeps its pk after the delete


@respx.mock
def test_client_built_after_the_deletion_keeps_its_entries(user: User) -> None:
    languages()
    data_deletion.delete_github_data(user)
    with GitHubClient.for_user(user) as client:  # the stale ``user`` object is not consulted
        client.get_languages("o/r")
    assert len(user_keys(user)) == 1


@respx.mock
def test_public_scope_never_checks_the_generation(user: User, django_assert_num_queries) -> None:
    languages()
    with (
        GitHubClient.for_user(user, cache_scope=PUBLIC_SCOPE) as client,
        django_assert_num_queries(0),
    ):
        client.get_languages("o/r")


def test_deletion_bumps_the_generation_and_clears_the_display_name(user: User) -> None:
    User.objects.filter(pk=user.pk).update(display_name="Octo")
    data_deletion.delete_github_data(user)
    data_deletion.delete_github_data(user)
    assert (user.github_cache_generation, user.display_name) == (2, "")  # the object, too
    user.save()  # a later full save keeps the bump
    user.refresh_from_db()
    assert (user.github_cache_generation, user.display_name) == (2, "")


@respx.mock
def test_failed_generation_check_removes_the_entry(user: User, caplog) -> None:
    languages()
    with (
        GitHubClient.for_user(user) as client,  # reads GitHubAccount, not User.objects
        patch.object(User.objects, "filter", side_effect=DatabaseError("down")),
        caplog.at_level(logging.WARNING),
    ):
        assert client.get_languages("o/r") == {"Go": 5}
    assert "generation check failed: DatabaseError" in caplog.text
    assert user_keys(user) == []  # fails closed: one cache miss, never a kept entry


def test_failed_purge_at_commit_queues_a_retry(
    user: User, django_capture_on_commit_callbacks, settings
) -> None:
    with (
        patch.object(data_deletion, "purge_user_github_cache", return_value=False),
        patch("github.tasks.purge_user_cache.apply_async") as retry,
        django_capture_on_commit_callbacks(execute=True),
    ):
        data_deletion.delete_github_data(user)
    retry.assert_called_once_with((user.pk,), countdown=settings.GITHUB_CACHE_BACKOFF_SECONDS)


def test_successful_purge_at_commit_queues_nothing(
    user: User, django_capture_on_commit_callbacks
) -> None:
    with (
        patch("github.tasks.purge_user_cache.apply_async") as retry,
        django_capture_on_commit_callbacks(execute=True),
    ):
        data_deletion.delete_github_data(user)
    retry.assert_not_called()


def test_a_broker_error_never_fails_the_deletion(
    signed_in_client, user: User, django_capture_on_commit_callbacks
) -> None:
    with (
        patch.object(data_deletion, "purge_user_github_cache", return_value=False),
        patch("github.tasks.purge_user_cache.apply_async", side_effect=ConnectionError("down")),
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = signed_in_client.delete("/api/v1/profile/github-data")
    assert response.status_code == 204
    user.refresh_from_db()
    assert user.github_cache_generation == 1


@override_settings(CELERY_TASK_ALWAYS_EAGER=False)
def test_purge_task_retries_while_the_cache_is_down() -> None:
    with (
        patch("github.tasks.purge_user_github_cache", return_value=False),
        patch.object(purge_user_cache, "retry", side_effect=CeleryRetry()) as retry,
        pytest.raises(CeleryRetry),
    ):
        purge_user_cache.apply(args=(7,), throw=True)
    retry.assert_called_once()


@pytest.mark.parametrize("eager", [False, True])
def test_purge_task_gives_up_on_its_last_try(eager: bool, caplog) -> None:
    retries = PURGE_ATTEMPTS - 1 if not eager else 0  # eager: the first try is the last
    with (
        override_settings(CELERY_TASK_ALWAYS_EAGER=eager),
        patch("github.tasks.purge_user_github_cache", return_value=False),
        patch.object(purge_user_cache, "retry") as retry,
        caplog.at_level(logging.WARNING),
    ):
        purge_user_cache.apply(args=(7,), retries=retries, throw=True)
    retry.assert_not_called()
    assert f"gave up after {PURGE_ATTEMPTS} tries" in caplog.text
