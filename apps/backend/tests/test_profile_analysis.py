"""ProfileAnalysisService, the standalone analysis job and the reanalyze command."""

from io import StringIO
from typing import cast
from unittest.mock import patch

import pytest
import respx
from django.core.management import CommandError, call_command
from django.test import override_settings

from developers.models import DeveloperProfile, DeveloperSkill, SkillEvidence
from developers.tasks import extract_developer_skills
from github.models import GitHubAccount
from jobs.models import SyncJob
from repositories.models import (
    Repository,
    RepositoryTopic,
)
from services.profiling.analysis import ProfileAnalysisError, ProfileAnalysisService

from .factories import GitHubAccountFactory

pytestmark = pytest.mark.django_db


def skills(user) -> dict[str, DeveloperSkill]:
    return {
        s.skill.slug: s
        for s in DeveloperSkill.objects.filter(profile__user=user).select_related("skill")
    }


def test_profile_created_with_defaults_and_config(synced) -> None:
    profile = ProfileAnalysisService(synced).run()
    assert profile.preferred_project_size == "any"
    assert profile.preferred_issue_difficulty == "unknown"
    assert profile.analysis_config["evidence_weights"]["readme"] == 0.20
    assert profile.analysis_config["taxonomy_version"]
    assert profile.summary.startswith("Works mostly in Go and Python.")
    assert profile.languages == [{"name": "Python", "bytes": 2000, "share": 1.0, "repo_count": 2}]
    assert profile.experience_level in {"beginner", "intermediate", "experienced"}

    found = skills(synced)
    assert {"python", "django", "docker", "kubernetes", "go"} <= set(found)
    python = found["python"]
    sources = sorted(python.evidence.values_list("source", flat=True))
    assert sources == ["language", "language", "readme"]
    assert found["go"].evidence.filter(source="repeated_contribution").exists()
    assert python.last_observed_at is not None
    assert found["docker"].confidence == 0.20  # README only

    interests = set(profile.interests.values_list("interest__slug", flat=True))
    assert "developer-tooling" in interests


def test_idempotent(synced) -> None:
    def snapshot():
        return sorted(
            SkillEvidence.objects.filter(developer_skill__profile__user=synced).values_list(
                "developer_skill__skill__slug",
                "developer_skill__confidence",
                "source",
                "repository_id",
                "detail",
            )
        )

    ProfileAnalysisService(synced).run()
    first, summary = snapshot(), DeveloperProfile.objects.get(user=synced).summary
    ProfileAnalysisService(synced).run()
    assert snapshot() == first
    assert DeveloperProfile.objects.get(user=synced).summary == summary
    assert DeveloperProfile.objects.filter(user=synced).count() == 1


def test_reanalysis_replaces_stale_conclusions(synced) -> None:
    ProfileAnalysisService(synced).run()
    assert "kubernetes" in skills(synced)
    RepositoryTopic.objects.filter(topic="kubernetes").delete()
    RepositoryTopic.objects.create(repository=Repository.objects.get(name="r2"), topic="terraform")
    ProfileAnalysisService(synced).run()
    found = skills(synced)
    assert "kubernetes" not in found
    assert "terraform" in found


def test_preferences_kept(synced) -> None:
    profile = ProfileAnalysisService(synced).run()
    DeveloperProfile.objects.filter(pk=profile.pk).update(preferred_project_size="small")
    ProfileAnalysisService(synced).run()
    assert DeveloperProfile.objects.get(pk=profile.pk).preferred_project_size == "small"


def test_failure_leaves_previous_profile_unchanged(synced) -> None:
    ProfileAnalysisService(synced).run()
    before = (DeveloperProfile.objects.get(user=synced).analyzed_at, set(skills(synced)))
    RepositoryTopic.objects.create(repository=Repository.objects.get(name="r2"), topic="rust")
    with (
        patch(
            "services.profiling.analysis.InterestEvidence.objects.bulk_create",
            side_effect=RuntimeError("db down"),
        ),
        pytest.raises(ProfileAnalysisError),
    ):
        ProfileAnalysisService(synced).run()
    assert (DeveloperProfile.objects.get(user=synced).analyzed_at, set(skills(synced))) == before


@pytest.mark.respx(assert_all_called=False)
def test_no_github_requests(synced, respx_mock: respx.MockRouter) -> None:
    ProfileAnalysisService(synced).run()
    assert len(respx_mock.calls) == 0


@override_settings(
    EVIDENCE_WEIGHTS={
        "readme": 0.10,
        "topic": 0.3,
        "language": 0.5,
        "dependency": 0.6,
        "commit": 0.8,
        "pull_request": 0.9,
        "repeated_contribution": 1.0,
    }
)
def test_weight_change_applies_on_reanalysis(synced) -> None:
    ProfileAnalysisService(synced).run()
    assert skills(synced)["docker"].confidence == 0.10


def test_sparse_account(user) -> None:
    profile = ProfileAnalysisService(user).run()
    assert profile.summary.startswith("Not enough public activity")
    assert not profile.skills.exists()
    assert profile.experience_level == "unknown"


# --- job and command -------------------------------------------------------------------


def test_analysis_job_completes(synced) -> None:
    job = SyncJob.objects.create(
        user=synced, job_type="profile_analysis", steps={"analysis": "pending"}
    )
    extract_developer_skills.delay(job.pk)
    job.refresh_from_db()
    assert (job.status, job.steps, job.error_code) == ("COMPLETED", {"analysis": "done"}, "")
    assert DeveloperProfile.objects.filter(user=synced).exists()


def test_analysis_job_failure(synced) -> None:
    job = SyncJob.objects.create(user=synced, job_type="profile_analysis")
    with patch(
        "developers.tasks.ProfileAnalysisService.run", side_effect=ProfileAnalysisError("x")
    ):
        extract_developer_skills.delay(job.pk)
    job.refresh_from_db()
    assert (job.status, job.error_code, job.steps) == (
        "FAILED",
        "analysis_failed",
        {"analysis": "failed"},
    )


def test_command_queues_one_job_per_synced_user(synced, django_capture_on_commit_callbacks):
    SyncJob.objects.create(user=synced, job_type="github_profile_sync", status="COMPLETED")
    never_synced = cast(GitHubAccount, GitHubAccountFactory()).user
    out = StringIO()
    with (
        patch("developers.tasks.extract_developer_skills.delay") as delay,
        django_capture_on_commit_callbacks(execute=True),
    ):
        call_command("reanalyze_profiles", stdout=out)
        call_command("reanalyze_profiles", stdout=out)  # second run: job still active
    assert delay.call_count == 1
    assert SyncJob.objects.filter(job_type="profile_analysis", user=synced).count() == 1
    assert not SyncJob.objects.filter(job_type="profile_analysis", user=never_synced).exists()
    assert "Queued 1" in out.getvalue()


def test_command_unknown_user(db) -> None:
    with pytest.raises(CommandError):
        call_command("reanalyze_profiles", "--user", "999999")
