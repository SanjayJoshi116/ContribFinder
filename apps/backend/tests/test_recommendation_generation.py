"""Recommendation generation job and freshness (Phase 5, group 5)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from developers.models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    Interest,
    Skill,
    SkillEvidence,
)
from jobs.models import SyncJob
from recommendations.models import Recommendation, RecommendationReason, ScoringConfig
from repositories.models import (
    Repository,
    RepositoryDependency,
    RepositoryLanguage,
    RepositorySnapshot,
    RepositoryTopic,
)
from services import jobs
from services.github.sync import JobCancelled
from services.ranking import freshness
from services.ranking.config import V2_PARAMS, V2_WEIGHTS
from services.ranking.service import RecommendationService

from .repo_fixtures import add_candidate, make_candidate_repo

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]


@pytest.fixture
def developer(user) -> DeveloperProfile:
    profile = DeveloperProfile.objects.create(
        user=user, analyzed_at=timezone.now() - timedelta(days=1)
    )
    for index, (slug, name, category, confidence) in enumerate(
        (("python", "Python", "language", 0.9), ("django", "Django", "framework", 0.8))
    ):
        skill = Skill.objects.create(slug=slug, name=name, category=category)
        ds = DeveloperSkill.objects.create(profile=profile, skill=skill, confidence=confidence)
        own_repo = make_candidate_repo(900 + index, f"me/{slug}-project")
        SkillEvidence.objects.create(developer_skill=ds, source="language", repository=own_repo)
    interest = Interest.objects.create(slug="developer-tooling", name="Developer tooling")
    DeveloperInterest.objects.create(profile=profile, interest=interest, strength=0.7)
    return profile


def ready_repo(
    github_id: int,
    full_name: str,
    *,
    languages=(("Python", 1000),),
    topics=(),
    deps=(),
    label="recently_active",
    **fields,
) -> Repository:
    repo = make_candidate_repo(
        github_id, full_name, lifecycle="recommendable", is_eligible=True, **fields
    )
    for language, size in languages:
        RepositoryLanguage.objects.create(repository=repo, language=language, bytes=size)
    for topic in topics:
        RepositoryTopic.objects.create(repository=repo, topic=topic)
    for name in deps:
        RepositoryDependency.objects.create(
            repository=repo, ecosystem="pypi", name=name, manifest_path="requirements.txt"
        )
    RepositorySnapshot.objects.create(
        repository=repo,
        captured_at=timezone.now(),
        stars=1,
        forks=0,
        open_issues=0,
        activity_label=label,
        thresholds_version="x",
        days_since_push=3,
        commits_90d=40,
        contributors=25,
    )
    return repo


@pytest.fixture
def pool(developer):
    django_tool = ready_repo(
        1,
        "encode/django-tool",
        topics=("django", "developer-tools"),
        deps=("django",),
        has_contributing=True,
        has_good_first_issue_label=True,
    )
    plain_py = ready_repo(2, "someone/pylib", label="low_activity")
    go_repo = ready_repo(3, "other/goserver", languages=(("Go", 1000),))
    for rank, repo in enumerate((go_repo, plain_py, django_tool), start=1):
        add_candidate(developer, repo, rank=rank)
    return {"django": django_tool, "plain": plain_py, "go": go_repo}


def running_job(user) -> SyncJob:
    return SyncJob.objects.create(
        user=user,
        job_type="recommendation_generation",
        status="RUNNING",
        steps={"recommendations": "pending"},
        started_at=timezone.now(),
    )


def generate(user) -> SyncJob:
    job = running_job(user)
    RecommendationService(job).run()
    SyncJob.objects.filter(pk=job.pk).update(status="COMPLETED", completed_at=timezone.now())
    job.refresh_from_db()
    return job


def test_generation_ranks_labels_and_explains(user, developer, pool, respx_mock) -> None:
    job = generate(user)
    recs = list(Recommendation.objects.filter(developer=developer).order_by("rank"))
    assert [r.repository.full_name for r in recs][:2] == ["encode/django-tool", "someone/pylib"]
    top = recs[0]
    assert top.scoring_config.version == "v2-deterministic"
    assert top.match_label == "strong"
    assert set(top.signal_scores) == set(V2_WEIGHTS)
    assert top.size == "medium" and top.activity_label == "recently_active"
    assert {"slug": "django", "name": "Django", "category": "framework", "matched": True} in (
        top.technologies
    )
    reason_types = [r.type for r in top.reasons.all()]
    assert {"skill", "language", "framework", "interest", "activity", "openness"} == set(
        reason_types
    )
    go = next((r for r in recs if r.repository_id == pool["go"].pk), None)
    assert go is None or "language" not in {r.type for r in go.reasons.all()}
    assert job.steps["recommendations"] == "done"
    assert job.metadata["config_version"] == "v2-deterministic"
    assert not respx_mock.calls


def test_regeneration_keeps_ids_and_drops_the_rest(user, developer, pool) -> None:
    generate(user)
    ids = dict(Recommendation.objects.values_list("repository_id", "pk"))
    Repository.objects.filter(pk=pool["plain"].pk).update(lifecycle="indexed", is_eligible=False)
    generate(user)
    after = dict(Recommendation.objects.values_list("repository_id", "pk"))
    assert pool["plain"].pk not in after
    assert after[pool["django"].pk] == ids[pool["django"].pk]
    assert not RecommendationReason.objects.filter(recommendation_id=ids[pool["plain"].pk])


def test_failure_during_write_keeps_previous_results(user, developer, pool, monkeypatch) -> None:
    generate(user)
    before = sorted(Recommendation.objects.values_list("pk", "rank", "score"))
    reasons_before = RecommendationReason.objects.count()
    Repository.objects.filter(pk=pool["plain"].pk).update(is_eligible=False)

    def boom(*args, **kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(RecommendationReason.objects, "bulk_create", boom)
    with pytest.raises(RuntimeError):
        RecommendationService(running_job(user)).run()
    assert sorted(Recommendation.objects.values_list("pk", "rank", "score")) == before
    assert RecommendationReason.objects.count() == reasons_before


def test_cancelled_generation_keeps_previous_results(user, developer, pool) -> None:
    generate(user)
    before = sorted(Recommendation.objects.values_list("pk", "rank"))
    job = running_job(user)
    jobs.cancel_active_syncs(user)  # what disconnect does
    with pytest.raises(JobCancelled):
        RecommendationService(job).run()
    assert sorted(Recommendation.objects.values_list("pk", "rank")) == before


def test_no_eligible_candidates(user, developer) -> None:
    add_candidate(developer, make_candidate_repo(5, lifecycle="discovered"))
    job = generate(user)
    assert not Recommendation.objects.exists()
    assert job.metadata["kept"] == 0


def test_min_score_filters(user, developer, pool, settings) -> None:
    settings.RECOMMENDATION_MIN_SCORE = 0.9
    generate(user)
    assert not Recommendation.objects.exists()


def test_discovery_completion_starts_generation(user, developer, monkeypatch) -> None:
    from repositories import tasks as repo_tasks

    monkeypatch.setattr(repo_tasks, "_discover", lambda job: None)
    queued: list[int] = []
    monkeypatch.setattr(
        "recommendations.tasks.generate_recommendations.delay", lambda pk: queued.append(pk)
    )
    discovery = SyncJob.objects.create(user=user, job_type="repository_discovery", status="PENDING")
    repo_tasks.generate_candidates.delay(discovery.pk)
    job = SyncJob.objects.get(job_type="recommendation_generation")
    assert job.status == "PENDING"
    again, created = jobs.start_recommendations(user)
    assert (again.pk if again else None, created) == (job.pk, False)


def test_generate_task_runs_the_service(user, developer, pool) -> None:
    from recommendations.tasks import generate_recommendations

    job = SyncJob.objects.create(user=user, job_type="recommendation_generation", status="PENDING")
    generate_recommendations.delay(job.pk)
    job.refresh_from_db()
    assert job.status == "COMPLETED"
    assert Recommendation.objects.filter(developer=developer).exists()


def test_missing_config_fails_permanently(user, developer, pool) -> None:
    from recommendations.tasks import generate_recommendations

    ScoringConfig.objects.update(is_active=False)
    job = SyncJob.objects.create(user=user, job_type="recommendation_generation", status="PENDING")
    generate_recommendations.delay(job.pk)
    job.refresh_from_db()
    assert (job.status, job.error_code) == ("FAILED", "no_scoring_config")


class TestFreshness:
    def due(self) -> list[int]:
        return [p.pk for p in freshness.due_profiles()]

    def test_never_generated_is_due(self, user, developer, pool) -> None:
        assert self.due() == [developer.pk]

    def test_current_is_not_due(self, user, developer, pool) -> None:
        generate(user)
        assert self.due() == []

    def test_refreshed_repository_is_due(self, user, developer, pool) -> None:
        generate(user)
        Repository.objects.filter(pk=pool["go"].pk).update(
            lifecycle_changed_at=timezone.now() + timedelta(seconds=1)
        )
        assert self.due() == [developer.pk]

    def test_reanalyzed_profile_is_due(self, user, developer, pool) -> None:
        generate(user)
        DeveloperProfile.objects.filter(pk=developer.pk).update(
            analyzed_at=timezone.now() + timedelta(seconds=1)
        )
        assert self.due() == [developer.pk]

    def test_new_active_config_is_due(self, user, developer, pool) -> None:
        generate(user)
        ScoringConfig.objects.update(is_active=False)
        ScoringConfig.objects.create(
            version="v3", weights=V2_WEIGHTS, params=V2_PARAMS, is_active=True
        )
        assert self.due() == [developer.pk]

    def test_sweep_starts_one_job_per_due_developer(
        self, user, developer, pool, monkeypatch
    ) -> None:
        monkeypatch.setattr("recommendations.tasks.generate_recommendations.delay", lambda pk: None)
        assert freshness.start_due_generations() == 1
        assert freshness.start_due_generations() == 0  # the active job is reused
        assert SyncJob.objects.filter(job_type="recommendation_generation").count() == 1
