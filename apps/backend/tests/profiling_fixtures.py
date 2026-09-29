"""Builders for ProfileInput snapshots used by the pure profiling tests."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import count
from typing import Any

from services.profiling.inputs import ContributionInput, DependencyInput, ProfileInput, RepoInput

NOW = datetime(2026, 9, 1, tzinfo=UTC)
_ids = count(1)


def repo(**kw: Any) -> RepoInput:
    n = next(_ids)
    deps = tuple(DependencyInput(eco, name, path) for eco, name, path in kw.pop("deps", ()))
    defaults: dict[str, Any] = {
        "id": n,
        "full_name": f"octocat/repo{n}",
        "pushed_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    return RepoInput(**{**defaults, **kw, "dependencies": deps})


def contribution(prs: int = 0, pushes: int = 0, **repo_kw: Any) -> ContributionInput:
    r = repo(**{"full_name": f"upstream/project{next(_ids)}", **repo_kw})
    return ContributionInput(r, prs, pushes, datetime(2026, 7, 1, tzinfo=UTC))


def profile(**kw: Any) -> ProfileInput:
    return ProfileInput(now=NOW, **kw)
