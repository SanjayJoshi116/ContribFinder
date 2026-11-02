"""Review sweep of ``jobs/`` (Bug_Backlog.md batch 36, JOB-1…JOB-10)."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.admin.sites import site
from django.db import connection
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from jobs.models import ACTIVE_STATUSES, SyncJob
from services.job_guard import is_stalled, stale_before
from services.jobs import _stale_running

from .shared_fixtures import assert_view_only, changelist_queries

pytestmark = pytest.mark.django_db

SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC


def make_job(user, status: str, *, age: timedelta = timedelta(0), job_type: str = SYNC) -> SyncJob:
    job = SyncJob.objects.create(user=user, job_type=job_type, status=status)
    SyncJob.objects.filter(pk=job.pk).update(updated_at=timezone.now() - age)
    job.refresh_from_db()
    return job


STALE = timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS + 60)


# --- View-only admin (JOB-1, JOB-2, JOB-5) -----------------------------------------------


def test_staff_cannot_add_change_or_delete_jobs(admin_user: User, user) -> None:
    assert_view_only(SyncJob, admin_user, make_job(user, "RUNNING"))
    assert site._registry[SyncJob].list_select_related == ("user",)


def test_change_page_is_view_only_and_saving_changes_nothing(admin_client: Client, user) -> None:
    job = make_job(user, "RUNNING", age=STALE)
    url = f"/admin/jobs/syncjob/{job.pk}/change/"
    page = admin_client.get(url)
    assert page.status_code == 200
    assert b'name="_save"' not in page.content
    assert admin_client.post(url, {}).status_code == 403
    assert admin_client.get("/admin/jobs/syncjob/add/").status_code == 403
    stored = SyncJob.objects.get(pk=job.pk)
    assert stored.updated_at == job.updated_at


def test_changelist_query_count_does_not_grow_with_rows(admin_client: Client, user) -> None:
    url = "/admin/jobs/syncjob/"
    make_job(user, "COMPLETED")
    one = changelist_queries(admin_client, url)
    for n in range(3):
        make_job(User.objects.create(username=f"u{n}"), "COMPLETED")
    assert changelist_queries(admin_client, url) == one


# --- One active-status list and the recovery index (JOB-4, JOB-6, JOB-8) ------------------


def test_database_conditions_use_the_active_statuses() -> None:
    values = [status.value for status in ACTIVE_STATUSES]
    meta = SyncJob._meta
    (constraint,) = meta.constraints
    index = next(i for i in meta.indexes if i.name == "syncjob_active_updated_idx")
    assert constraint.condition.children == [("status__in", values)]  # type: ignore[attr-defined]
    assert index.condition.children == [("status__in", values)]
    assert SyncJob.ACTIVE_STATUSES is ACTIVE_STATUSES
    assert not hasattr(SyncJob, "is_active")


def test_recovery_index_exists_in_the_database() -> None:
    with connection.cursor() as cursor:
        found = connection.introspection.get_constraints(cursor, SyncJob._meta.db_table)
    assert found["syncjob_active_updated_idx"]["columns"] == ["updated_at"]


def test_recovery_runs_expire_after_one_interval() -> None:
    entry = settings.CELERY_BEAT_SCHEDULE["recover-stale-jobs"]
    assert entry["options"] == {"expires": settings.JOB_RECOVERY_INTERVAL_SECONDS}


# --- Stalled jobs (JOB-3) --------------------------------------------------------------


def test_is_stalled_agrees_with_the_query_on_both_sides_of_the_cutoff(user) -> None:
    now = timezone.now()
    cutoff = now - stale_before(now)
    # One active job per type (unique constraint): each status gets its own type or is finished.
    rows = [
        ("RUNNING", cutoff + timedelta(seconds=5), SyncJob.JobType.GITHUB_PROFILE_SYNC),
        ("RUNNING", cutoff - timedelta(seconds=5), SyncJob.JobType.PROFILE_ANALYSIS),
        ("PENDING", STALE, SyncJob.JobType.REPOSITORY_DISCOVERY),
        ("RETRYING", STALE, SyncJob.JobType.RECOMMENDATION_GENERATION),
        ("COMPLETED", STALE, SyncJob.JobType.GITHUB_PROFILE_SYNC),
        ("FAILED", STALE, SyncJob.JobType.GITHUB_PROFILE_SYNC),
        ("CANCELLED", STALE, SyncJob.JobType.GITHUB_PROFILE_SYNC),
    ]
    jobs = [make_job(user, status, age=age, job_type=job_type) for status, age, job_type in rows]
    stalled = set(SyncJob.objects.filter(_stale_running(now)).values_list("pk", flat=True))
    assert {job.pk for job in jobs if is_stalled(job, now)} == stalled == {jobs[0].pk}


def test_status_reports_a_dead_running_sync_as_stalled_and_leaves_it(
    signed_in_client: APIClient, user
) -> None:
    job = make_job(user, "RUNNING", age=STALE)
    body = signed_in_client.get("/api/v1/sync/status").json()
    assert (body["job"]["status"], body["job"]["stalled"]) == ("RUNNING", True)
    stored = SyncJob.objects.get(pk=job.pk)
    assert (stored.status, stored.updated_at) == ("RUNNING", job.updated_at)


@pytest.mark.parametrize("status", ["RUNNING", "PENDING", "RETRYING", "COMPLETED", "FAILED"])
def test_status_reports_other_jobs_as_not_stalled(
    signed_in_client: APIClient, user, status: str
) -> None:
    make_job(user, status, age=timedelta(0) if status == "RUNNING" else STALE)
    assert signed_in_client.get("/api/v1/sync/status").json()["job"]["stalled"] is False


@pytest.mark.parametrize(
    ("path", "job_type"),
    [
        ("/api/v1/discovery/status", SyncJob.JobType.REPOSITORY_DISCOVERY),
        ("/api/v1/recommendations/status", SyncJob.JobType.RECOMMENDATION_GENERATION),
    ],
)
def test_discovery_and_generation_status_carry_stalled(
    signed_in_client: APIClient, user, path: str, job_type: str
) -> None:
    make_job(user, "RUNNING", age=STALE, job_type=job_type)
    assert signed_in_client.get(path).json()["job"]["stalled"] is True


def test_starting_over_a_stalled_sync_replaces_it(signed_in_client: APIClient, user) -> None:
    stalled = make_job(user, "RUNNING", age=STALE)
    with patch("github.tasks.sync_github_profile.delay"):
        response = signed_in_client.post("/api/v1/profile/sync")
    assert response.status_code == 202
    assert response.json()["id"] != stalled.pk
    assert response.json()["stalled"] is False
    stalled.refresh_from_db()
    assert (stalled.status, stalled.error_code) == ("FAILED", "worker_lost")
