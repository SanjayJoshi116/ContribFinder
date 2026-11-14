"""Candidate filtering (design D4): a stage of its own, between search and ranking.

``prefilter`` runs on search payloads before anything becomes a candidate; ``eligibility``
re-checks the repository-level rules on analyzed data. Both return a reason code, or None
when the repository passes. No writes: stored repositories are read for their topics and
whether they have dependencies (annotate ``has_dependencies`` and prefetch ``topics`` when
checking many).
"""

from __future__ import annotations

from collections.abc import Collection, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from django.conf import settings
from django.db.models import Exists, OuterRef

from repositories.models import Lifecycle, Repository, RepositoryDependency

ARCHIVED = "archived"
FORK = "fork"
INACTIVE = "inactive"
NO_LICENSE = "no_license"
FEW_STARS = "few_stars"
OWN_REPOSITORY = "own_repository"
NOT_CODE = "not_code"
REPOSITORY_UNAVAILABLE = "repository_unavailable"
NAME_RELEASED = "name_released"  # gave its name to another repository; resolved by GitHub ID


class RepoLike(Protocol):
    """A search result (``GitHubRepo``) or a stored ``Repository``."""

    @property
    def owner_login(self) -> str: ...
    @property
    def full_name(self) -> str: ...
    @property
    def stars(self) -> int: ...
    @property
    def is_fork(self) -> bool: ...
    @property
    def is_archived(self) -> bool: ...
    @property
    def pushed_at(self) -> datetime | None: ...
    @property
    def license_spdx(self) -> str: ...
    @property
    def primary_language(self) -> str: ...


@dataclass(frozen=True)
class FilterConfig:
    min_stars: int
    max_push_age_days: int
    excluded_topics: frozenset[str] = frozenset()

    @classmethod
    def from_settings(cls) -> FilterConfig:
        return cls(
            settings.DISCOVERY_MIN_STARS,
            settings.DISCOVERY_MAX_PUSH_AGE_DAYS,
            frozenset(t.lower() for t in settings.DISCOVERY_EXCLUDED_TOPICS),
        )


def prefilter(
    repo: RepoLike,
    *,
    login: str,
    owned: Set[str],
    now: datetime,
    cfg: FilterConfig,
    check_stars: bool = True,
) -> str | None:
    """``owned``: lowercased full names of the developer's own repositories. Stars are not
    checked for previously interacted repositories (``check_stars=False``)."""
    if repo.owner_login.lower() == login.lower() or repo.full_name.lower() in owned:
        return OWN_REPOSITORY
    reason = _repository_rules(
        archived=repo.is_archived,
        fork=repo.is_fork,
        pushed_at=repo.pushed_at,
        license_spdx=repo.license_spdx,
        now=now,
        cfg=cfg,
    )
    if reason is not None:
        return reason
    if check_stars and repo.stars < cfg.min_stars:
        return FEW_STARS
    # A stored repository (previously interacted) brings its dependencies; a search result has
    # none, so a suspected list passes here and ``stored_result_not_code`` checks it once stored.
    stored = stored_has_dependencies(repo) if isinstance(repo, Repository) else None
    if not_code(repo.full_name, _topics(repo), repo.primary_language, cfg, has_dependencies=stored):
        return NOT_CODE
    return None


def eligibility(
    repo: Repository,
    *,
    now: datetime,
    cfg: FilterConfig,
    topics: Collection[str] | None = None,
    has_dependencies: bool | None = None,
) -> str | None:
    """``topics`` and ``has_dependencies``, when given, are the stored values the caller
    already holds (an analysis that just wrote them); otherwise they are read."""
    if repo.lifecycle == Lifecycle.FAILED:
        return REPOSITORY_UNAVAILABLE
    reason = _repository_rules(
        archived=repo.is_archived,
        fork=repo.is_fork,
        pushed_at=repo.pushed_at,
        license_spdx=repo.license_spdx,
        now=now,
        cfg=cfg,
    )
    if reason is None and stored_not_code(
        repo, cfg, topics=topics, has_dependencies=has_dependencies
    ):
        return NOT_CODE
    return reason


def not_code(
    full_name: str,
    topics: Collection[str],
    primary_language: str,
    cfg: FilterConfig,
    *,
    has_dependencies: bool | None,
) -> bool:
    """Curated lists and documentation repositories are not contribution targets: no
    detected programming language, or a suspected list (named ``awesome`` / ``awesome-*``, or
    tagged with an excluded topic) without manifest dependencies. ``has_dependencies`` None
    (not analyzed yet) lets a suspected list through: its analysis decides."""
    if not primary_language:
        return True
    return suspected_list(full_name, topics, cfg) and has_dependencies is False


def suspected_list(full_name: str, topics: Collection[str], cfg: FilterConfig) -> bool:
    name = full_name.rsplit("/", 1)[-1].lower()
    if name == "awesome" or name.startswith("awesome-"):
        return True
    return any(t.lower() in cfg.excluded_topics for t in topics)


def stored_not_code(
    repo: Repository,
    cfg: FilterConfig,
    *,
    topics: Collection[str] | None = None,
    has_dependencies: bool | None = None,
) -> bool:
    """``not_code`` on a stored repository, with its dependencies once they were fetched.
    Given ``topics`` / ``has_dependencies`` are used instead of reading them."""
    return not_code(
        repo.full_name,
        _topics(repo) if topics is None else topics,
        repo.primary_language,
        cfg,
        has_dependencies=(
            stored_has_dependencies(repo) if has_dependencies is None else has_dependencies
        ),
    )


def stored_result_not_code(result: RepoLike, repo: Repository, cfg: FilterConfig) -> bool:
    """``not_code`` for a search result that passed ``prefilter`` and was just stored as
    ``repo``: the result's topics, the stored row's dependencies (an earlier analysis may have
    found it is a list). Dependencies are read only for a suspected list."""
    topics = _topics(result)  # the row's topic rows are the result's, without a query
    return suspected_list(result.full_name, topics, cfg) and stored_not_code(
        repo, cfg, topics=topics
    )


def has_dependencies_annotation() -> Exists:
    """``has_dependencies`` for querysets that check many repositories."""
    return Exists(RepositoryDependency.objects.filter(repository=OuterRef("pk")))


def stored_has_dependencies(repo: Repository) -> bool | None:
    """Whether a stored repository declares manifest dependencies; None before they were
    fetched. Reads the ``has_dependencies`` annotation when present."""
    if repo.dependencies_synced_at is None:
        return None
    annotated: bool | None = getattr(repo, "has_dependencies", None)
    if annotated is not None:
        return annotated
    return repo.dependencies.exists()


def _topics(repo: RepoLike) -> Collection[str]:
    """A search result carries its topics; a stored repository has them as rows (read
    through ``all()``, so a ``prefetch_related("topics")`` is used)."""
    if isinstance(repo, Repository):
        return [t.topic for t in repo.topics.all()] if repo.pk else []
    topics: Collection[str] = getattr(repo, "topics", ())
    return topics


def _repository_rules(
    *,
    archived: bool,
    fork: bool,
    pushed_at: datetime | None,
    license_spdx: str,
    now: datetime,
    cfg: FilterConfig,
) -> str | None:
    if archived:
        return ARCHIVED
    if fork:
        return FORK
    if pushed_at is None or pushed_at < now - timedelta(days=cfg.max_push_age_days):
        return INACTIVE
    # NOASSERTION ("Other") means GitHub found a license file it could not classify: present.
    if not license_spdx:
        return NO_LICENSE
    return None
