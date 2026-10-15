"""Candidate filtering (design D4): a stage of its own, between search and ranking.

``prefilter`` runs on search payloads before anything becomes a candidate; ``eligibility``
re-checks the repository-level rules on analyzed data. Both return a reason code, or None
when the repository passes. Pure functions.
"""

from __future__ import annotations

from collections.abc import Collection, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from django.conf import settings

from repositories.models import Lifecycle, Repository

ARCHIVED = "archived"
FORK = "fork"
INACTIVE = "inactive"
NO_LICENSE = "no_license"
FEW_STARS = "few_stars"
OWN_REPOSITORY = "own_repository"
NOT_CODE = "not_code"
REPOSITORY_UNAVAILABLE = "repository_unavailable"


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
    if reason is None and check_stars and repo.stars < cfg.min_stars:
        return FEW_STARS
    if reason is None and not_code(repo.full_name, _topics(repo), repo.primary_language, cfg):
        return NOT_CODE
    return reason


def eligibility(repo: Repository, *, now: datetime, cfg: FilterConfig) -> str | None:
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
    if reason is None and not_code(repo.full_name, _topics(repo), repo.primary_language, cfg):
        return NOT_CODE
    return reason


def not_code(
    full_name: str, topics: Collection[str], primary_language: str, cfg: FilterConfig
) -> bool:
    """Curated lists and documentation repositories are not contribution targets (design D4):
    named ``awesome`` / ``awesome-*``, tagged with an excluded topic, or without any detected
    programming language."""
    name = full_name.rsplit("/", 1)[-1].lower()
    if name == "awesome" or name.startswith("awesome-"):
        return True
    if any(t.lower() in cfg.excluded_topics for t in topics):
        return True
    return not primary_language


def _topics(repo: RepoLike) -> Collection[str]:
    """A search result carries its topics; a stored repository has them as rows."""
    if isinstance(repo, Repository):
        return list(repo.topics.values_list("topic", flat=True)) if repo.pk else []
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
