"""Review sweep of ``developers/`` (Bug_Backlog.md batch 37, DEV-1…DEV-9)."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from developers.api import ProfileListPagination
from developers.models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    Interest,
    InterestEvidence,
    Skill,
    SkillEvidence,
)
from jobs.models import SyncJob
from services.profiling.taxonomy import INTERESTS, SKILLS

from .shared_fixtures import assert_view_only, changelist_queries

pytestmark = pytest.mark.django_db

ADMINS = [DeveloperProfile, Skill, DeveloperSkill, Interest, DeveloperInterest]
ANALYZE = "developers.tasks.extract_developer_skills.delay"
SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC


def make_profile(user: User) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def add_skill(
    profile: DeveloperProfile, slug: str, confidence: float, name: str = ""
) -> DeveloperSkill:
    skill, _ = Skill.objects.get_or_create(
        slug=slug, defaults={"name": name or slug, "category": "language"}
    )
    return DeveloperSkill.objects.create(profile=profile, skill=skill, confidence=confidence)


def add_interest(profile: DeveloperProfile, slug: str, strength: float) -> DeveloperInterest:
    interest, _ = Interest.objects.get_or_create(slug=slug, defaults={"name": slug})
    return DeveloperInterest.objects.create(profile=profile, interest=interest, strength=strength)


# --- Read-only admin (DEV-1, DEV-2, DEV-9) -------------------------------------------------


@pytest.mark.parametrize("model", ADMINS, ids=lambda m: m.__name__)
def test_staff_cannot_add_change_or_delete_developer_data(admin_user: User, model) -> None:
    assert_view_only(model, admin_user)


def test_deleting_a_skill_through_the_admin_is_refused(admin_client: Client, user) -> None:
    add_skill(make_profile(user), "python", 0.9)
    skill = Skill.objects.get(slug="python")
    delete = admin_client.post(f"/admin/developers/skill/{skill.pk}/delete/", {"post": "yes"})
    assert delete.status_code == 403
    response = admin_client.post(
        "/admin/developers/skill/",
        {"action": "delete_selected", "_selected_action": [skill.pk], "post": "yes"},
    )
    assert response.status_code in {200, 302}
    assert DeveloperSkill.objects.filter(skill=skill).exists()


@pytest.mark.parametrize(
    ("path", "build"),
    [
        ("developerprofile", lambda user: make_profile(user)),
        ("developerskill", lambda user: add_skill(make_profile(user), f"s{user.pk}", 0.5)),
        ("developerinterest", lambda user: add_interest(make_profile(user), f"i{user.pk}", 0.5)),
    ],
)
def test_changelist_query_count_does_not_grow_with_rows(
    admin_client: Client, path: str, build
) -> None:
    url = f"/admin/developers/{path}/"
    build(User.objects.create(username="first"))
    one = changelist_queries(admin_client, url)
    for n in range(3):
        build(User.objects.create(username=f"more{n}"))
    assert changelist_queries(admin_client, url) == one


def test_interest_page_lists_its_evidence(admin_client: Client, user) -> None:
    interest = add_interest(make_profile(user), "security", 0.7)
    InterestEvidence.objects.create(
        developer_interest=interest, source="topic", detail='"security-tools"'
    )
    page = admin_client.get(f"/admin/developers/developerinterest/{interest.pk}/change/")
    assert page.status_code == 200
    assert b"security-tools" in page.content


# --- Evidence and list order (DEV-3, DEV-7) ------------------------------------------------


def test_undated_evidence_comes_last(signed_in_client: APIClient, user) -> None:
    profile = make_profile(user)
    skill = add_skill(profile, "python", 0.9)
    interest = add_interest(profile, "security", 0.7)
    now = timezone.now()
    for detail, when in [("undated", None), ("old", now - timedelta(days=9)), ("new", now)]:
        SkillEvidence.objects.create(
            developer_skill=skill, source="language", detail=detail, observed_at=when
        )
        InterestEvidence.objects.create(
            developer_interest=interest, source="topic", detail=detail, observed_at=when
        )
    for path in ("/api/v1/profile/skills", "/api/v1/profile/interests"):
        evidence = signed_in_client.get(path).json()["results"][0]["evidence"]
        assert [e["detail"] for e in evidence] == ["new", "old", "undated"], path
    assert [e.detail for e in skill.evidence.all()] == ["new", "old", "undated"]


@pytest.mark.parametrize("path", ["/api/v1/profile/skills", "/api/v1/profile/interests"])
def test_tied_rows_page_in_a_stable_order(signed_in_client: APIClient, user, path: str) -> None:
    profile = make_profile(user)
    # Created in reverse slug order, so pk order differs from slug order. Same score and same
    # name: only the pk separates them.
    slugs = ["same-c", "same-b", "same-a"]
    if "skills" in path:
        for slug in slugs:
            add_skill(profile, slug, 0.5, name="Same")
        key = "skill"
    else:
        for slug in slugs:
            interest = Interest.objects.create(slug=slug, name="Same")
            DeveloperInterest.objects.create(profile=profile, interest=interest, strength=0.5)
        key = "interest"
    seen = [
        signed_in_client.get(f"{path}?page_size=1&page={page}").json()["results"][0][key]["slug"]
        for page in (1, 2, 3)
    ]
    assert seen == slugs  # every row once, in pk order


# --- Reanalysis command (DEV-4, DEV-5) -----------------------------------------------------


def completed_sync(user: User) -> None:
    SyncJob.objects.create(
        user=user, job_type=SYNC, status="COMPLETED", completed_at=timezone.now()
    )


def run(*args: str) -> str:
    out = StringIO()
    with patch(ANALYZE):
        call_command("reanalyze_profiles", *args, stdout=out)
    return out.getvalue()


def test_reanalysis_skips_inactive_and_syncing_users(user) -> None:
    completed_sync(user)
    inactive = User.objects.create(username="gone", is_active=False)
    completed_sync(inactive)
    syncing = User.objects.create(username="busy")
    completed_sync(syncing)
    SyncJob.objects.create(user=syncing, job_type=SYNC, status="RUNNING")

    assert run() == "Queued 1 analysis job(s); 0 already active; 1 syncing (skipped).\n"
    analyzed = SyncJob.objects.filter(job_type=SyncJob.JobType.PROFILE_ANALYSIS)
    assert list(analyzed.values_list("user", flat=True)) == [user.pk]


def test_reanalysis_of_one_inactive_user_names_the_reason() -> None:
    inactive = User.objects.create(username="gone", is_active=False)
    completed_sync(inactive)
    with pytest.raises(CommandError, match="inactive"):
        run("--user", str(inactive.pk))


def test_a_stalled_sync_does_not_hold_back_reanalysis(user) -> None:
    completed_sync(user)
    stalled = SyncJob.objects.create(user=user, job_type=SYNC, status="RUNNING")
    SyncJob.objects.filter(pk=stalled.pk).update(updated_at=timezone.now() - timedelta(days=1))
    assert run().startswith("Queued 1 analysis job(s)")


# --- Catalog guard (DEV-6) -----------------------------------------------------------------


def test_catalogs_fit_on_one_profile_page() -> None:
    limit = ProfileListPagination.max_page_size
    message = "the SPA reads one page: page through `next` in features/profile/api.ts first"
    assert len(SKILLS) <= limit, message
    assert len(INTERESTS) <= limit, message
