"""Skill evidence collectors for repositories, dependencies and contributions
(spec: skill-detection). Pure functions over ``ProfileInput``; forks never count."""

from __future__ import annotations

from collections.abc import Iterable

from .inputs import ContributionInput, Evidence, ProfileInput, RepoInput
from .taxonomy import skill_for_dependency, skill_for_linguist, skill_for_topic


def repo_language_skills(repo: RepoInput, min_share: float) -> dict[str, str]:
    """``{skill slug: detail}`` for catalog languages that are primary or reach ``min_share``."""
    found: dict[str, str] = {}
    languages = dict(repo.languages)
    if repo.primary_language and repo.primary_language not in languages:
        languages[repo.primary_language] = 0
    for language in sorted(languages, key=lambda lang: -languages[lang]):
        share = repo.language_share(language)
        is_primary = language == repo.primary_language
        if not is_primary and share < min_share:
            continue
        if slug := skill_for_linguist(language):
            detail = f"{language} · {round(share * 100)}% of code" if share else language
            found.setdefault(slug, detail + (" (primary language)" if is_primary else ""))
    return found


def repo_topic_skills(repo: RepoInput) -> dict[str, str]:
    found: dict[str, str] = {}
    for topic in repo.topics:
        if slug := skill_for_topic(topic):
            found.setdefault(slug, f'"{topic}"')
    return found


def language_skills(profile: ProfileInput, min_share: float) -> list[Evidence]:
    return [
        Evidence(slug, "language", repo.id, detail, repo.pushed_at)
        for repo in profile.own_work
        for slug, detail in repo_language_skills(repo, min_share).items()
    ]


def topic_skills(profile: ProfileInput) -> list[Evidence]:
    return [
        Evidence(slug, "topic", repo.id, detail, repo.pushed_at)
        for repo in profile.own_work
        for slug, detail in repo_topic_skills(repo).items()
    ]


def dependency_skills(profile: ProfileInput) -> list[Evidence]:
    evidence = []
    for repo in profile.own_work:
        seen: set[str] = set()
        for dep in repo.dependencies:
            slug = skill_for_dependency(dep.ecosystem, dep.name)
            if slug and slug not in seen:
                seen.add(slug)
                detail = f"{dep.manifest_path}: {dep.name}"[:255]
                evidence.append(Evidence(slug, "dependency", repo.id, detail, repo.pushed_at))
    return evidence


def _contributed_skills(contribution: ContributionInput, min_share: float) -> Iterable[str]:
    repo = contribution.repo
    return dict.fromkeys([*repo_language_skills(repo, min_share), *repo_topic_skills(repo)])


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def contribution_skills(
    profile: ProfileInput, min_share: float, repeated_min_prs: int
) -> list[Evidence]:
    """pull_request / commit / repeated_contribution evidence, one record per contributed
    repository and skill, attributed through the repository's languages and topics."""
    evidence = []
    for contribution in profile.contributions:
        repo = contribution.repo
        when = contribution.observed_at
        prs, pushes = contribution.merged_pr_count, contribution.push_count
        for slug in _contributed_skills(contribution, min_share):
            if prs > 0:
                detail = _plural(prs, "merged pull request", "merged pull requests")
                evidence.append(Evidence(slug, "pull_request", repo.id, detail[:255], when))
            if pushes > 0:
                detail = _plural(pushes, "recent push", "recent pushes")
                evidence.append(Evidence(slug, "commit", repo.id, detail[:255], when))
            if prs >= repeated_min_prs:
                detail = f"{prs} merged pull requests to the same repository"
                evidence.append(
                    Evidence(slug, "repeated_contribution", repo.id, detail[:255], when)
                )
    return evidence
