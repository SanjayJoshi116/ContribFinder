"""Export a developer's stored matching inputs as a benchmark developer (spec:
recommendation-evaluation "Export a developer snapshot"; design D5).

Reads the same features generation reads, plus eligible issues. No GitHub calls. The result
holds no username, name, email, GitHub id, avatar or token, and no judgments. Repositories the
user interacted with are left out unless asked for: that set identifies the person.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.conf import settings

from developers.models import DeveloperProfile
from repositories.models import CandidateDiscovery, DiscoverySource, UserRepository
from services.matching.features import load_candidates, load_developer
from services.matching.issues import load_issues

from .dataset import FORMAT

NOTE = (
    "Exported from stored data for hand judgment. Add judgments (0 not relevant, 1 relevant, "
    "2 highly relevant) by hand before using this developer in a benchmark."
)


class NotAnalyzed(Exception):
    pass


def interacted_repository_ids(profile: DeveloperProfile) -> set[int]:
    """Repositories the user contributed to or that entered the pool as previously interacted."""
    ids = set(
        CandidateDiscovery.objects.filter(
            candidate__developer=profile, source=DiscoverySource.PREVIOUSLY_INTERACTED
        ).values_list("candidate__repository_id", flat=True)
    )
    ids.update(
        UserRepository.objects.filter(user_id=profile.user_id).values_list(
            "repository_id", flat=True
        )
    )
    return ids


def export_developer(
    user_id: int, developer_id: str, now: datetime, *, include_interacted: bool = False
) -> tuple[dict[str, Any], int]:
    """The dataset and the number of interacted candidates left out."""
    profile = DeveloperProfile.objects.filter(user_id=user_id, analyzed_at__isnull=False).first()
    if profile is None:
        raise NotAnalyzed(f"User {user_id} has no analyzed developer profile.")
    dev = load_developer(profile)
    candidates = load_candidates(profile, include_dismissed=True, now=now)
    dropped = 0
    if not include_interacted:
        interacted = interacted_repository_ids(profile)
        kept = [repo for repo in candidates if repo.id not in interacted]
        dropped, candidates = len(candidates) - len(kept), kept
    issues = load_issues([r.id for r in candidates], now, settings.ISSUE_MAX_AGE_DAYS)

    repositories: dict[str, Any] = {}
    for repo in candidates:
        snapshot = repo.snapshot
        repositories[repo.full_name] = {
            "description": repo.description,
            "languages": [list(pair) for pair in repo.languages],
            "topics": list(repo.topics),
            "dependencies": [list(pair) for pair in repo.dependencies],
            "has_contributing": repo.has_contributing,
            "has_issue_templates": repo.has_issue_templates,
            "has_good_first_issue_label": repo.has_good_first_issue_label,
            "has_help_wanted_label": repo.has_help_wanted_label,
            "snapshot": {
                "activity_label": snapshot.activity_label,
                "days_since_push": snapshot.days_since_push,
                "commits_90d": snapshot.commits_90d,
                "prs_merged_90d": snapshot.prs_merged_90d,
                "contributors": snapshot.contributors,
            }
            if snapshot
            else None,
            "issues": [
                {
                    "number": issue.number,
                    "labels": list(issue.labels),
                    "contribution_type": issue.contribution_type,
                    "difficulty": issue.difficulty,
                    "technologies": list(issue.technologies),
                    "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                }
                for issue in sorted(issues.get(repo.id, []), key=lambda i: i.number)
            ],
        }
    return {
        "format": FORMAT,
        "name": f"export-{developer_id}",
        "description": NOTE,
        "repositories": repositories,
        "developers": [
            {
                "id": developer_id,
                "description": NOTE,
                "experience_level": dev.experience_level,
                "skills": {
                    slug: {
                        "confidence": skill.confidence,
                        "category": skill.category,
                        "repo_count": skill.repo_count,
                    }
                    for slug, skill in sorted(dev.skills.items())
                },
                "interests": {slug: value for slug, (_, value) in sorted(dev.interests.items())},
                "candidates": [
                    {"repository": repo.full_name, "best_search_rank": repo.best_search_rank}
                    for repo in candidates
                ],
                "judgments": {},
            }
        ],
    }, dropped
