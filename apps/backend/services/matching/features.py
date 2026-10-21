"""Loading the inputs of matching (design D3). The only part of matching that touches the
database; everything downstream works on these frozen values."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Exists, Min, OuterRef, Prefetch

from developers.models import DeveloperInterest, DeveloperProfile, DeveloperSkill
from feedback.models import DismissedRepository
from repositories.models import RepositoryCandidate, RepositorySnapshot
from services.repositories.lifecycle import SCORABLE


@dataclass(frozen=True)
class SkillFeature:
    confidence: float
    category: str
    name: str
    repo_count: int  # repositories the developer's evidence for it comes from


@dataclass(frozen=True)
class DeveloperFeatures:
    skills: dict[str, SkillFeature]
    interests: dict[str, tuple[str, float]]  # slug -> (name, strength)
    experience_level: str = "unknown"  # internal: issue difficulty fit only, never shown

    def confidence(self, slug: str) -> float:
        skill = self.skills.get(slug)
        return skill.confidence if skill else 0.0


@dataclass(frozen=True)
class SnapshotData:
    activity_label: str
    days_since_push: int | None
    commits_90d: int | None
    prs_merged_90d: int | None
    contributors: int | None


@dataclass(frozen=True)
class RepoData:
    id: int
    full_name: str
    description: str
    languages: tuple[tuple[str, int], ...]
    topics: tuple[str, ...]
    dependencies: tuple[tuple[str, str], ...]
    has_contributing: bool
    has_issue_templates: bool
    has_good_first_issue_label: bool
    has_help_wanted_label: bool
    snapshot: SnapshotData | None
    best_search_rank: int | None


def load_developer(profile: DeveloperProfile) -> DeveloperFeatures:
    skills = (
        DeveloperSkill.objects.filter(profile=profile)
        .select_related("skill")
        .annotate(repo_count=Count("evidence__repository", distinct=True))
    )
    interests = DeveloperInterest.objects.filter(profile=profile).select_related("interest")
    return DeveloperFeatures(
        skills={
            s.skill.slug: SkillFeature(s.confidence, s.skill.category, s.skill.name, s.repo_count)
            for s in skills
        },
        interests={i.interest.slug: (i.interest.name, i.strength) for i in interests},
        experience_level=profile.experience_level,
    )


def load_candidates(
    profile: DeveloperProfile, *, include_dismissed: bool = False
) -> list[RepoData]:
    """The developer's scorable candidates: eligible repositories that finished analysis
    (stale data included) and, unless ``include_dismissed``, that the user has not dismissed.
    A fixed number of queries whatever the pool size."""
    candidates = RepositoryCandidate.objects.filter(
        developer=profile, repository__lifecycle__in=SCORABLE, repository__is_eligible=True
    )
    if not include_dismissed:
        dismissed = DismissedRepository.objects.filter(
            user_id=profile.user_id, repository=OuterRef("repository")
        )
        candidates = candidates.exclude(Exists(dismissed))
    candidates = (
        candidates.select_related("repository")
        .annotate(best_rank=Min("discoveries__search_rank"))
        .prefetch_related(
            "repository__languages",
            "repository__topics",
            "repository__dependencies",
            Prefetch(
                "repository__snapshots",
                queryset=RepositorySnapshot.objects.order_by("-captured_at", "-pk"),
                to_attr="ordered_snapshots",
            ),
        )
        .order_by("repository__full_name")
    )
    result = []
    for candidate in candidates:
        repo = candidate.repository
        latest = repo.ordered_snapshots[0] if repo.ordered_snapshots else None  # type: ignore[attr-defined]
        result.append(
            RepoData(
                id=repo.pk,
                full_name=repo.full_name,
                description=repo.description,
                languages=tuple((lang.language, lang.bytes) for lang in repo.languages.all()),
                topics=tuple(t.topic for t in repo.topics.all()),
                dependencies=tuple((d.ecosystem, d.name) for d in repo.dependencies.all()),
                has_contributing=bool(repo.has_contributing),
                has_issue_templates=bool(repo.has_issue_templates),
                has_good_first_issue_label=bool(repo.has_good_first_issue_label),
                has_help_wanted_label=bool(repo.has_help_wanted_label),
                snapshot=_snapshot(latest),
                best_search_rank=candidate.best_rank,
            )
        )
    return result


def _snapshot(snapshot: RepositorySnapshot | None) -> SnapshotData | None:
    if snapshot is None:
        return None
    return SnapshotData(
        activity_label=snapshot.activity_label,
        days_since_push=snapshot.days_since_push,
        commits_90d=snapshot.commits_90d,
        prs_merged_90d=snapshot.prs_merged_90d,
        contributors=snapshot.contributors,
    )
