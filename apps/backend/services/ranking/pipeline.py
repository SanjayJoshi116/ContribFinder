"""The in-memory ranking stage shared by generation and evaluation (spec:
recommendation-evaluation; design D1). Pure: issues come through ``issues_for``.

technologies → signals → issue matching (for candidates that pass the relevance gate)
→ score → rank.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from services.matching import signals as sig
from services.matching.features import DeveloperFeatures, RepoData
from services.matching.issues import NO_MATCH, IssueFeature, match_issues
from services.matching.technologies import repository_technologies

from .score import BASIS_SCORE, Scored, has_relevance, rank, score_candidate

IssuesFor = Callable[[Sequence[int]], Mapping[int, Iterable[IssueFeature]]]


def rank_pool(
    dev: DeveloperFeatures,
    candidates: Iterable[RepoData],
    weights: Mapping[str, float],
    params: Mapping[str, Any],
    issues_for: IssuesFor,
    *,
    min_score: float,
    top_n: int | None,
) -> list[Scored]:
    """Rank a developer's candidates under one configuration. ``issues_for`` is called once,
    with the ids of the candidates that pass the relevance gate, and only when the
    configuration matches issues (v1 does not) and weights issue fit or difficulty fit above
    0. ``min_score`` is the installation default: a configuration's own ``min_score`` (and
    ``min_score_basis``) wins."""
    computed = []
    for repo in candidates:
        techs = repository_technologies(
            repo.languages, repo.topics, repo.dependencies, params["tech_sources"]
        )
        computed.append((repo, techs, sig.compute(repo, techs, dev, params)))
    issue_params = params.get("issues")
    if not (weights.get("issue_fit", 0.0) > 0 or weights.get("difficulty_fit", 0.0) > 0):
        issue_params = None  # nothing to gain from matching issues: every candidate NO_MATCH
    issues = (
        issues_for([repo.id for repo, _, signals in computed if has_relevance(signals, weights)])
        if issue_params
        else {}
    )
    scored = []
    for repo, techs, signals in computed:
        match = match_issues(issues[repo.id], dev, issue_params) if repo.id in issues else NO_MATCH
        signals = {**signals, "issue_fit": match.issue_fit, "difficulty_fit": match.difficulty_fit}
        scored.append(score_candidate(repo, techs, signals, weights, params, match))
    return rank(
        scored,
        min_score=params.get("min_score", min_score),
        top_n=top_n,
        basis=params.get("min_score_basis", BASIS_SCORE),
    )
