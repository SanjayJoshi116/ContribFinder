"""Phase 3 sync steps: dependencies, contributions and analysis."""

from unittest.mock import patch

import httpx
import pytest
import respx
from django.test import override_settings

from developers.models import DeveloperProfile
from github.tasks import sync_github_profile
from jobs.models import SyncJob
from repositories.models import Repository, RepositoryDependency, UserRepository
from services.github.sync import GitHubSyncService, initial_steps
from services.profiling.analysis import ProfileAnalysisError

from .test_github_sync import API, SYNC, mock_github, repo_json

pytestmark = pytest.mark.django_db


@pytest.fixture
def job(user):
    return SyncJob.objects.create(
        user=user, job_type=SYNC, status="RUNNING", steps=initial_steps(), attempts=1
    )


def run(job) -> None:
    GitHubSyncService(job).run()


def calls(path: str) -> int:
    return sum(1 for c in respx.mock.calls if c.request.url.path == path)


def mock_manifests(router: respx.MockRouter, full_name: str, files: dict[str, str]) -> None:
    router.get(f"{API}/repos/{full_name}/contents/").respond(
        200,
        json=[{"name": n, "type": "file", "size": len(t)} for n, t in files.items()]
        + [{"name": "src", "type": "dir", "size": 0}],
    )
    for name, text in files.items():
        router.get(f"{API}/repos/{full_name}/contents/{name}").respond(200, text=text)


def pr(repo: str) -> dict[str, object]:
    return {"repository_url": f"{API}/repos/{repo}", "pull_request": {"merged_at": None}}


def mock_contributions(router: respx.MockRouter, prs: list[str], pushes: tuple[str, ...] = ()):
    router.get(f"{API}/search/issues").respond(200, json={"items": [pr(r) for r in prs]})
    router.get(f"{API}/users/octocat/events/public").respond(
        200,
        json=[
            {"type": "PushEvent", "repo": {"name": r}, "created_at": "2026-08-01T10:00:00Z"}
            for r in pushes
        ],
    )
    for n, name in enumerate(sorted(set(prs) | set(pushes))):
        owner = name.split("/")[0]
        router.get(f"{API}/repos/{name}").respond(
            200,
            json=repo_json(
                50 + n,
                owner=owner,
                full_name=name,
                topics=["security"],
                pushed="2026-08-01T10:00:00Z",
            ),
        )
        router.get(f"{API}/repos/{name}/languages").respond(200, json={"Go": 100})


# --- dependencies ------------------------------------------------------------------------


@respx.mock
def test_manifests_stored_per_repository(job, user) -> None:
    mock_github(respx.mock, repos=[repo_json(1), repo_json(2)])
    mock_manifests(
        respx.mock,
        "octocat/r1",
        {"package.json": '{"dependencies": {"react": "^19"}, "devDependencies": {"vite": "7"}}'},
    )
    run(job)
    deps = RepositoryDependency.objects.filter(repository__name="r1")
    assert set(deps.values_list("ecosystem", "name", "manifest_path")) == {
        ("npm", "react", "package.json"),
        ("npm", "vite", "package.json"),
    }
    assert not RepositoryDependency.objects.filter(repository__name="r2").exists()
    job.refresh_from_db()
    assert job.steps["dependencies"] == "done"


@respx.mock
def test_forbidden_repository_skipped(job) -> None:
    mock_github(respx.mock, repos=[repo_json(1), repo_json(2)])
    respx.mock.get(f"{API}/repos/octocat/r1/contents/").respond(403)
    run(job)
    job.refresh_from_db()
    assert job.status == "RUNNING"  # the service does not finish jobs; the step is done
    assert job.steps["dependencies"] == "done"


@respx.mock
@override_settings(GITHUB_MANIFEST_MAX_BYTES=10)
def test_oversized_manifest_not_fetched(job) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    mock_manifests(respx.mock, "octocat/r1", {"requirements.txt": "django\nflask\ncelery\n"})
    run(job)
    assert calls("/repos/octocat/r1/contents/requirements.txt") == 0


@respx.mock
@override_settings(GITHUB_MANIFEST_MAX_REPOS=1)
def test_manifest_cap_and_forks(job) -> None:
    # r1 < r2 < r3 by push date; r3 is a fork, so only r2 is read under a cap of 1.
    mock_github(respx.mock, repos=[repo_json(1), repo_json(2), repo_json(3, fork=True)])
    run(job)
    assert calls("/repos/octocat/r2/contents/") == 1
    assert calls("/repos/octocat/r1/contents/") == 0
    assert calls("/repos/octocat/r3/contents/") == 0
    job.refresh_from_db()
    assert job.metadata["dependencies_capped"] is True


@respx.mock
def test_retry_resumes_dependencies_without_refetching(job) -> None:
    mock_github(respx.mock, repos=[repo_json(1), repo_json(2)])
    respx.mock.get(f"{API}/repos/octocat/r1/contents/").mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json=[])]
    )
    with pytest.raises(Exception, match="502"):
        run(job)
    run(job)
    assert calls("/repos/octocat/r2/contents/") == 1  # r2 (pushed later) finished before
    assert calls("/repos/octocat/r1/contents/") == 2
    assert calls("/users/octocat/repos") == 1


# --- contributions -----------------------------------------------------------------------


@respx.mock
def test_contributions_stored_and_linked(job, user) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    mock_contributions(
        respx.mock,
        prs=["pallets/flask"] * 3 + ["psf/requests"],
        pushes=("psf/requests",),
    )
    run(job)
    links = {
        link.repository.full_name: link
        for link in UserRepository.objects.filter(user=user, relation="contributor")
    }
    assert set(links) == {"pallets/flask", "psf/requests"}
    assert (links["pallets/flask"].merged_pr_count, links["pallets/flask"].push_count) == (3, 0)
    assert (links["psf/requests"].merged_pr_count, links["psf/requests"].push_count) == (1, 1)
    assert links["psf/requests"].last_contributed_at is not None
    flask = Repository.objects.get(full_name="pallets/flask")
    assert list(flask.languages.values_list("language", flat=True)) == ["Go"]
    assert list(flask.topics.values_list("topic", flat=True)) == ["security"]


@respx.mock
def test_own_repositories_excluded(job, user) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    mock_contributions(respx.mock, prs=[], pushes=("octocat/r1",))
    run(job)
    assert not UserRepository.objects.filter(user=user, relation="contributor").exists()


@respx.mock
def test_stale_contributor_link_removed(job, user) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    mock_contributions(respx.mock, prs=["pallets/flask"])
    run(job)
    SyncJob.objects.filter(pk=job.pk).update(status="COMPLETED")
    second = SyncJob.objects.create(
        user=user, job_type=SYNC, status="RUNNING", steps=initial_steps()
    )
    respx.mock.get(f"{API}/search/issues").respond(200, json={"items": []})
    run(second)
    assert not UserRepository.objects.filter(user=user, relation="contributor").exists()
    assert UserRepository.objects.filter(user=user, relation="owner").count() == 1


@respx.mock
@override_settings(GITHUB_CONTRIB_MAX_REPOS=1)
def test_contribution_cap(job, user) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    mock_contributions(respx.mock, prs=["a/one", "b/two", "b/two"])
    run(job)
    linked = UserRepository.objects.filter(user=user, relation="contributor")
    assert list(linked.values_list("repository__full_name", flat=True)) == ["b/two"]
    job.refresh_from_db()
    assert job.metadata["contrib_capped"] is True
    assert calls("/repos/a/one") == 0


@respx.mock
def test_search_422_skips_step_and_sync_completes(user) -> None:
    pending = SyncJob.objects.create(
        user=user, job_type=SYNC, status="PENDING", steps=initial_steps()
    )
    mock_github(respx.mock, repos=[repo_json(1)])
    respx.mock.get(f"{API}/search/issues").respond(422)
    sync_github_profile.delay(pending.pk)
    pending.refresh_from_db()
    assert pending.status == "COMPLETED"
    assert pending.steps["contributions"] == "skipped"
    assert pending.steps["analysis"] == "done"


@respx.mock
def test_retry_resumes_contributions_without_refetching(job, user) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    mock_contributions(respx.mock, prs=["a/one", "b/two", "b/two"])
    respx.mock.get(f"{API}/repos/a/one").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=repo_json(9, owner="a", full_name="a/one")),
        ]
    )
    with pytest.raises(Exception, match="503"):
        run(job)
    run(job)
    assert calls("/search/issues") == 1
    assert calls("/repos/b/two") == 1  # most PRs, stored before the failure
    assert UserRepository.objects.filter(user=user, relation="contributor").count() == 2


# --- analysis ----------------------------------------------------------------------------


@respx.mock
def test_analysis_step_builds_profile(job, user) -> None:
    mock_github(respx.mock, repos=[repo_json(1)], readme="## Skills\nPython, Docker")
    run(job)
    profile = DeveloperProfile.objects.get(user=user)
    assert set(profile.skills.values_list("skill__slug", flat=True)) >= {"python", "docker"}


@respx.mock
def test_analysis_failure_fails_job_and_keeps_github_data(user) -> None:
    pending = SyncJob.objects.create(
        user=user, job_type=SYNC, status="PENDING", steps=initial_steps()
    )
    mock_github(respx.mock, repos=[repo_json(1)])
    with (
        patch(
            "services.github.sync.ProfileAnalysisService.run",
            side_effect=ProfileAnalysisError("boom"),
        ),
        patch.object(sync_github_profile, "retry") as retry,
    ):
        sync_github_profile.delay(pending.pk)
    retry.assert_not_called()
    pending.refresh_from_db()
    assert pending.status == "FAILED"
    assert pending.error_code == "analysis_failed"
    assert pending.steps["analysis"] == "failed"
    assert pending.steps["contributions"] == "done"
    assert Repository.objects.filter(user_links__user=user).exists()


# --- repository list ---------------------------------------------------------------------


@respx.mock
def test_repository_list_excludes_contributed(job, user, signed_in_client) -> None:
    mock_github(respx.mock, repos=[repo_json(1), repo_json(3)])
    mock_contributions(respx.mock, prs=["a/one", "b/two", "c/three"])
    run(job)
    body = signed_in_client.get("/api/v1/profile/repositories").json()
    assert sorted(r["full_name"] for r in body["results"]) == ["octocat/r1", "octocat/r3"]


def test_old_job_without_new_steps_serializes(user, signed_in_client) -> None:
    SyncJob.objects.create(
        user=user,
        job_type=SYNC,
        status="COMPLETED",
        steps=dict.fromkeys(["profile", "readme", "repositories", "languages", "topics"], "done"),
    )
    steps = signed_in_client.get("/api/v1/sync/status").json()["job"]["steps"]
    assert steps["analysis"] == "pending"
    assert len(steps) == 8
