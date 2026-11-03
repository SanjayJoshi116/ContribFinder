"""Immutable snapshot of a user's stored GitHub data that every profiling function reads
(design D5). Built once by the analysis service; collectors never touch the database."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .text import strip_html_comments


@dataclass(frozen=True)
class DependencyInput:
    ecosystem: str
    name: str
    manifest_path: str


@dataclass(frozen=True)
class RepoInput:
    id: int
    full_name: str
    description: str = ""
    primary_language: str = ""
    languages: dict[str, int] = field(default_factory=dict)
    topics: tuple[str, ...] = ()
    dependencies: tuple[DependencyInput, ...] = ()
    pushed_at: datetime | None = None
    is_fork: bool = False

    def language_share(self, language: str) -> float:
        total = sum(self.languages.values())
        return self.languages.get(language, 0) / total if total else 0.0


@dataclass(frozen=True)
class ContributionInput:
    repo: RepoInput
    merged_pr_count: int = 0
    push_count: int = 0
    last_contributed_at: datetime | None = None

    @property
    def observed_at(self) -> datetime | None:
        """When evidence from this contribution was observed: the contribution's own time, else
        the repository's last push."""
        return self.last_contributed_at or self.repo.pushed_at


@dataclass(frozen=True)
class ProfileInput:
    now: datetime
    readme: str = ""
    readme_observed_at: datetime | None = None
    account_created_at: datetime | None = None
    owned: tuple[RepoInput, ...] = ()
    contributions: tuple[ContributionInput, ...] = ()

    @property
    def own_work(self) -> tuple[RepoInput, ...]:
        """Owned repositories that are the user's own work (forks excluded)."""
        return tuple(r for r in self.owned if not r.is_fork)

    def __post_init__(self) -> None:
        # Normalized once for every consumer (evidence, interests, experience, summary):
        # commented-out README content is never read (PROF-3), and contributions to forked
        # repositories never count (PROF-8, also for experience).
        object.__setattr__(self, "readme", strip_html_comments(self.readme))
        object.__setattr__(
            self, "contributions", tuple(c for c in self.contributions if not c.repo.is_fork)
        )


@dataclass(frozen=True)
class Evidence:
    """One piece of evidence for a skill or interest (``key`` is its catalog slug)."""

    key: str
    source: str
    repository_id: int | None
    detail: str
    observed_at: datetime | None
