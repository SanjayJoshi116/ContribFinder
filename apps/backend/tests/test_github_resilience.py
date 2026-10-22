"""github-error-resilience: one repository or response never fails a whole sync."""

from unittest.mock import patch

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from django.test import override_settings
from django.utils import timezone

from e2e.builders import make_candidate_repo
from github.models import GitHubProfile
from github.tasks import sync_github_profile
from jobs.models import SyncJob
from repositories.models import Repository, RepositoryLanguage, UserRepository
from services.github.storage import replace_languages
from services.github.sync import GitHubSyncService, initial_steps

from .test_github_client import SECONDARY_MESSAGES
from .test_github_sync import API, PROFILE, SYNC, mock_github, repo_json, run

pytestmark = pytest.mark.django_db

LANGUAGES = rf"{API}/repos/octocat/r\d+/languages"


@pytest.fixture
def job(user):
    return SyncJob.objects.create(
        user=user, job_type=SYNC, status="RUNNING", steps=initial_steps(), attempts=1
    )


@pytest.fixture
def pending_job(user):
    return SyncJob.objects.create(user=user, job_type=SYNC, status="PENDING", steps=initial_steps())


def r1_languages(answer: httpx.Response) -> None:
    """Replace mock_github's languages route (same pattern, so respx swaps it): r1 gets
    ``answer``, every other repository the default breakdown."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/r1/languages"):
            return answer
        return httpx.Response(200, json={"Python": 7000, "TypeScript": 3000})

    respx.get(url__regex=LANGUAGES).mock(side_effect=respond)


def seed_repo(n: int, languages: dict[str, int]) -> Repository:
    repo = make_candidate_repo(100 + n, f"octocat/r{n}")
    replace_languages(repo, languages)
    return repo


@respx.mock
def test_undecryptable_token_fails_auth_without_requests(pending_job) -> None:
    with override_settings(TOKEN_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
        sync_github_profile.delay(pending_job.pk)
    pending_job.refresh_from_db()
    assert pending_job.status == "FAILED"
    assert pending_job.error_code == "github_auth_invalid"
    assert not respx.calls


@respx.mock
def test_blocked_repository_languages_are_kept_and_skipped(job) -> None:
    blocked = seed_repo(1, {"Go": 5000})
    mock_github(respx.mock, repos=[repo_json(1), repo_json(3)])
    r1_languages(httpx.Response(451))
    run(job)

    job.refresh_from_db()
    assert job.metadata["languages_skipped"] == [blocked.pk]
    assert dict(blocked.languages.values_list("language", "bytes")) == {"Go": 5000}
    other = Repository.objects.get(full_name="octocat/r3")
    assert set(other.languages.values_list("language", flat=True)) == {"Python", "TypeScript"}
    assert job.steps["languages"] == "done"


@respx.mock
@override_settings(CELERY_TASK_ALWAYS_EAGER=False)  # with a worker; eager mode never retries
def test_secondary_limit_on_languages_is_retried_not_skipped(pending_job) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    r1_languages(
        httpx.Response(
            403, json={"message": SECONDARY_MESSAGES[0]}, headers={"X-RateLimit-Remaining": "4000"}
        )
    )
    with (
        patch.object(sync_github_profile, "retry", side_effect=RuntimeError("retry")) as retry,
        pytest.raises(RuntimeError),
    ):
        sync_github_profile.apply(args=(pending_job.pk,), throw=True)
    assert retry.call_args.kwargs["countdown"] >= 60
    pending_job.refresh_from_db()
    assert pending_job.status == "RETRYING"
    assert pending_job.metadata.get("languages_skipped") == []


@respx.mock
@pytest.mark.parametrize("status", [403, 451])
def test_blocked_profile_readme_keeps_stored_readme(job, user, status: int) -> None:
    GitHubProfile.objects.create(
        user=user,
        github_id=424242,  # PROFILE["id"]
        login="octocat",
        has_profile_readme=True,
        profile_readme="## Skills\nRust",
        synced_at=timezone.now(),
    )
    mock_github(respx.mock, repos=[repo_json(1)])
    respx.get(f"{API}/repos/octocat/octocat/readme").respond(status)
    run(job)

    job.refresh_from_db()
    assert job.steps["readme"] == "skipped"
    assert job.steps["analysis"] == "done"
    profile = GitHubProfile.objects.get(user=user)
    assert (profile.has_profile_readme, profile.profile_readme) == (True, "## Skills\nRust")


@respx.mock
def test_repository_deleted_before_topics_step(job) -> None:
    mock_github(respx.mock, repos=[repo_json(1), repo_json(3)])
    service = GitHubSyncService(job)
    original = service._step_topics

    def delete_then_topics(client):
        Repository.objects.filter(full_name="octocat/r1").delete()
        return original(client)

    service._step_topics = delete_then_topics  # type: ignore[method-assign]
    service.run()

    r3 = Repository.objects.get(full_name="octocat/r3")
    assert set(r3.topics.values_list("topic", flat=True)) == {"topic3", "shared"}
    assert job.steps["topics"] == "done"


@respx.mock
def test_rename_on_github_updates_auth_me(signed_in_client, job) -> None:
    mock_github(respx.mock, repos=[])
    renamed = {**PROFILE, "login": "octo-cat", "avatar_url": "https://avatars.test/new.png"}
    respx.get(f"{API}/user").respond(200, json=renamed)
    respx.get(f"{API}/repos/octo-cat/octo-cat/readme").respond(404)
    respx.get(f"{API}/users/octo-cat/repos").respond(200, json=[])
    respx.get(f"{API}/users/octo-cat/events/public").respond(200, json=[])
    run(job)

    body = signed_in_client.get("/api/v1/auth/me").json()
    assert body["github_username"] == "octo-cat"
    assert body["avatar_url"] == "https://avatars.test/new.png"


@respx.mock
def test_renamed_contributed_repository_is_followed(job, user) -> None:
    mock_github(respx.mock, repos=[])
    respx.get(f"{API}/search/issues").respond(
        200,
        json={
            "total_count": 1,
            "items": [
                {
                    "repository_url": f"{API}/repos/old-org/tool",
                    "pull_request": {"merged_at": "2026-09-01T10:00:00Z"},
                }
            ],
        },
    )
    respx.get(f"{API}/repos/old-org/tool").respond(
        301, headers={"Location": f"{API}/repositories/55"}
    )
    current = repo_json(55, owner="new-org", pushed="2026-09-01T10:00:00Z")
    current.update(name="tool", full_name="new-org/tool")
    respx.get(f"{API}/repositories/55").respond(200, json=current)
    respx.get(f"{API}/repos/new-org/tool/languages").respond(200, json={"Rust": 900})
    run(job)

    link = UserRepository.objects.get(user=user, relation=UserRepository.Relation.CONTRIBUTOR)
    assert link.repository.full_name == "new-org/tool"
    assert link.merged_pr_count == 1
    assert RepositoryLanguage.objects.filter(repository=link.repository, language="Rust").exists()
