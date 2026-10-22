"""Refresh rebuilds the pipeline: sync → discovery → recommendations (Phase 8a, group 5)."""

import pytest
from rest_framework.test import APIClient

from jobs.models import SyncJob
from recommendations.models import Recommendation
from services.errors import PermanentJobError

from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]


@pytest.fixture
def stages(monkeypatch):
    """Stub every stage runner; each appends its name. Tasks run inline (no REDIS_URL)."""
    order: list[str] = []
    monkeypatch.setattr("github.tasks._run", lambda job: order.append("sync"))
    monkeypatch.setattr("repositories.tasks._discover", lambda job: order.append("discovery"))
    monkeypatch.setattr("recommendations.tasks._generate", lambda job: order.append("generation"))
    return order


def refresh(client: APIClient, capture) -> None:
    with capture(execute=True):
        assert client.post("/api/v1/profile/sync").status_code == 202


def test_full_refresh_runs_stages_in_order(
    signed_in_client: APIClient,
    user,
    developer,
    stages,
    django_capture_on_commit_callbacks,
) -> None:
    refresh(signed_in_client, django_capture_on_commit_callbacks)
    assert stages == ["sync", "discovery", "generation"]
    jobs = list(SyncJob.objects.filter(user=user).order_by("created_at"))
    assert [(j.job_type, j.status) for j in jobs] == [
        ("github_profile_sync", "COMPLETED"),
        ("repository_discovery", "COMPLETED"),
        ("recommendation_generation", "COMPLETED"),
    ]


class DiscoveryBroke(PermanentJobError):
    code = "discovery_broke"


def test_failed_discovery_starts_no_generation(
    signed_in_client: APIClient,
    user,
    developer,
    pool,
    stages,
    monkeypatch,
    django_capture_on_commit_callbacks,
) -> None:
    generate(user)
    before = sorted(Recommendation.objects.values_list("pk", "rank", "score"))

    def broken(job):
        stages.append("discovery")
        raise DiscoveryBroke("boom")

    monkeypatch.setattr("repositories.tasks._discover", broken)
    refresh(signed_in_client, django_capture_on_commit_callbacks)
    assert stages == ["sync", "discovery"]
    discovery = SyncJob.objects.get(job_type="repository_discovery")
    assert (discovery.status, discovery.error_code) == ("FAILED", "discovery_broke")
    assert SyncJob.objects.filter(job_type="recommendation_generation").count() == 1  # setup's
    assert sorted(Recommendation.objects.values_list("pk", "rank", "score")) == before
