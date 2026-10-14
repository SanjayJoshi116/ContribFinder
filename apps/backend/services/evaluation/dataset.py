"""Benchmark datasets (spec: recommendation-evaluation "Benchmark dataset", "Dataset
validation"; design D2). Loading validates the whole file, collecting every error, and
converts it to the frozen matching inputs that ``rank_pool`` takes. No database access.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from developers.models import ExperienceLevel, IssueDifficulty, SkillCategory
from issues.models import ContributionType
from repositories.models import ActivityLabel
from services.issues.labels import CATEGORIES as ISSUE_LABELS
from services.matching.features import DeveloperFeatures, RepoData, SkillFeature, SnapshotData
from services.matching.issues import IssueFeature
from services.profiling.taxonomy import INTERESTS_BY_SLUG, SKILLS_BY_SLUG

FORMAT = 1
DATASETS_DIR = Path(__file__).resolve().parents[2] / "evaluation"
DEFAULT_DATASET = DATASETS_DIR / "benchmark-v1.json"
GRADES = (0, 1, 2)


class DatasetError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid benchmark dataset:\n  " + "\n  ".join(errors))


@dataclass(frozen=True)
class BenchmarkDeveloper:
    id: str
    description: str
    features: DeveloperFeatures
    candidates: tuple[RepoData, ...]
    issues: Mapping[int, list[IssueFeature]]  # repository id -> eligible issues
    judgments: Mapping[str, int]  # repository full name -> grade


@dataclass(frozen=True)
class Dataset:
    name: str
    description: str
    developers: tuple[BenchmarkDeveloper, ...]
    repository_count: int
    source: str = field(default="")


def load(path: Path | str = DEFAULT_DATASET) -> Dataset:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DatasetError([f"{path}: {exc}"]) from exc
    return parse(raw, source=str(path))


def parse(raw: Any, source: str = "") -> Dataset:
    errors: list[str] = []
    if not isinstance(raw, dict):
        raise DatasetError(["dataset: must be a JSON object"])
    if raw.get("format") != FORMAT:
        raise DatasetError([f"format: unknown format version {raw.get('format')!r}"])
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        errors.append("name: required")
    repos_raw = raw.get("repositories")
    devs_raw = raw.get("developers")
    if not isinstance(repos_raw, dict):
        errors.append("repositories: must be an object keyed by full name")
        repos_raw = {}
    if not isinstance(devs_raw, list) or not devs_raw:
        errors.append("developers: must be a non-empty list")
        devs_raw = []

    # Ids are assigned by sorted name: RepoData and IssueFeature need ints, nothing keeps them.
    repo_ids = {full_name: index for index, full_name in enumerate(sorted(repos_raw), start=1)}
    repos: dict[str, dict[str, Any]] = {}
    issues: dict[int, list[IssueFeature]] = {}
    issue_id = 0
    for full_name, data in repos_raw.items():
        where = f"repository {full_name}"
        repo = _repository(data, where, errors)
        if repo is None:
            continue
        repos[full_name] = repo
        found = []
        for index, item in enumerate(repo["issues"]):
            issue_id += 1
            issue = _issue(item, issue_id, repo_ids[full_name], f"{where} issue {index}", errors)
            if issue is not None:
                found.append(issue)
        issues[repo_ids[full_name]] = found

    developers = []
    seen: set[str] = set()
    for index, item in enumerate(devs_raw):
        dev_id = item.get("id") if isinstance(item, dict) else None
        where = f"developer {dev_id or index}"
        if not isinstance(dev_id, str) or not dev_id:
            errors.append(f"{where}: id required")
            continue
        if dev_id in seen:
            errors.append(f"{where}: duplicate id")
            continue
        seen.add(dev_id)
        dev = _developer(item, where, repos, repo_ids, issues, errors)
        if dev is not None:
            developers.append(dev)

    if errors:
        raise DatasetError(errors)
    return Dataset(
        name=str(name),
        description=str(raw.get("description", "")),
        developers=tuple(developers),
        repository_count=len(repos),
        source=source,
    )


def _unit(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 0 <= value <= 1


def _count(value: Any) -> bool:
    return value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)


def _str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _repository(data: Any, where: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        errors.append(f"{where}: must be an object")
        return None
    before = len(errors)
    languages = data.get("languages", [])
    if not isinstance(languages, list) or not all(
        isinstance(p, list) and len(p) == 2 and isinstance(p[0], str) and _count(p[1])
        for p in languages
    ):
        errors.append(f"{where}: languages must be [name, bytes] pairs")
    dependencies = data.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(p, list) and len(p) == 2 and all(isinstance(v, str) for v in p)
        for p in dependencies
    ):
        errors.append(f"{where}: dependencies must be [ecosystem, name] pairs")
    if not _str_list(data.get("topics", [])):
        errors.append(f"{where}: topics must be a list of strings")
    for flag in (
        "has_contributing",
        "has_issue_templates",
        "has_good_first_issue_label",
        "has_help_wanted_label",
    ):
        if not isinstance(data.get(flag, False), bool):
            errors.append(f"{where}: {flag} must be true or false")
    snapshot = data.get("snapshot")
    if snapshot is not None:
        if not isinstance(snapshot, dict):
            errors.append(f"{where}: snapshot must be an object or null")
        else:
            if snapshot.get("activity_label") not in ActivityLabel.values:
                errors.append(f"{where}: unknown activity_label {snapshot.get('activity_label')!r}")
            for key in ("days_since_push", "commits_90d", "prs_merged_90d", "contributors"):
                if not _count(snapshot.get(key)):
                    errors.append(f"{where}: snapshot {key} must be a count or null")
    if not isinstance(data.get("issues", []), list):
        errors.append(f"{where}: issues must be a list")
    if len(errors) > before:
        return None
    return {
        "description": str(data.get("description", "")),
        "languages": tuple((lang, size) for lang, size in languages),
        "topics": tuple(data.get("topics", [])),
        "dependencies": tuple((eco, name) for eco, name in dependencies),
        "has_contributing": data.get("has_contributing", False),
        "has_issue_templates": data.get("has_issue_templates", False),
        "has_good_first_issue_label": data.get("has_good_first_issue_label", False),
        "has_help_wanted_label": data.get("has_help_wanted_label", False),
        "snapshot": SnapshotData(
            activity_label=snapshot["activity_label"],
            days_since_push=snapshot.get("days_since_push"),
            commits_90d=snapshot.get("commits_90d"),
            prs_merged_90d=snapshot.get("prs_merged_90d"),
            contributors=snapshot.get("contributors"),
        )
        if snapshot
        else None,
        "issues": data.get("issues", []),
    }


def _issue(
    data: Any, issue_id: int, repo_id: int, where: str, errors: list[str]
) -> IssueFeature | None:
    if not isinstance(data, dict):
        errors.append(f"{where}: must be an object")
        return None
    before = len(errors)
    number = data.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        errors.append(f"{where}: number must be a positive integer")
        number = 0
    labels = data.get("labels", [])
    if not _str_list(labels) or any(label not in ISSUE_LABELS for label in labels):
        errors.append(f"{where}: labels must be canonical issue labels, got {labels!r}")
    ctype = data.get("contribution_type", ContributionType.UNKNOWN)
    if ctype not in ContributionType.values:
        errors.append(f"{where}: unknown contribution_type {ctype!r}")
    difficulty = data.get("difficulty", IssueDifficulty.UNKNOWN)
    if difficulty not in IssueDifficulty.values:
        errors.append(f"{where}: unknown difficulty {difficulty!r}")
    techs = data.get("technologies", [])
    if not _str_list(techs):
        errors.append(f"{where}: technologies must be a list of skill slugs")
    else:
        for slug in techs:
            if slug not in SKILLS_BY_SLUG:
                errors.append(f"{where}: unknown technology {slug!r}")
    updated_at = None
    if (raw_updated := data.get("updated_at")) is not None:
        try:
            updated_at = datetime.fromisoformat(str(raw_updated))
        except ValueError:
            errors.append(f"{where}: updated_at must be an ISO 8601 time")
    if len(errors) > before:
        return None
    return IssueFeature(
        id=issue_id,
        repository_id=repo_id,
        number=number,
        labels=tuple(labels),
        contribution_type=ctype,
        difficulty=difficulty,
        technologies=tuple(techs),
        updated_at=updated_at,
    )


def _developer(
    data: dict[str, Any],
    where: str,
    repos: Mapping[str, dict[str, Any]],
    repo_ids: Mapping[str, int],
    issues: Mapping[int, list[IssueFeature]],
    errors: list[str],
) -> BenchmarkDeveloper | None:
    before = len(errors)
    level = data.get("experience_level", ExperienceLevel.UNKNOWN)
    if level not in ExperienceLevel.values:
        errors.append(f"{where}: unknown experience_level {level!r}")

    skills: dict[str, SkillFeature] = {}
    skills_raw = data.get("skills", {})
    if not isinstance(skills_raw, dict):
        errors.append(f"{where}: skills must be an object keyed by slug")
        skills_raw = {}
    for slug, skill in skills_raw.items():
        if slug not in SKILLS_BY_SLUG:
            errors.append(f"{where}: unknown skill {slug!r}")
            continue
        if not isinstance(skill, dict) or not _unit(skill.get("confidence")):
            errors.append(f"{where}: skill {slug} confidence must be within 0..1")
            continue
        category = skill.get("category", SKILLS_BY_SLUG[slug].category)
        if category not in SkillCategory.values:
            errors.append(f"{where}: skill {slug} has unknown category {category!r}")
            continue
        repo_count = skill.get("repo_count", 0)
        if not _count(repo_count):
            errors.append(f"{where}: skill {slug} repo_count must be a count")
            continue
        skills[slug] = SkillFeature(
            float(skill["confidence"]), category, SKILLS_BY_SLUG[slug].name, repo_count
        )

    interests: dict[str, tuple[str, float]] = {}
    interests_raw = data.get("interests", {})
    if not isinstance(interests_raw, dict):
        errors.append(f"{where}: interests must be an object keyed by slug")
        interests_raw = {}
    for slug, strength in interests_raw.items():
        if slug not in INTERESTS_BY_SLUG:
            errors.append(f"{where}: unknown interest {slug!r}")
        elif not _unit(strength):
            errors.append(f"{where}: interest {slug} strength must be within 0..1")
        else:
            interests[slug] = (INTERESTS_BY_SLUG[slug].name, float(strength))

    candidates: list[RepoData] = []
    pool: set[str] = set()
    candidates_raw = data.get("candidates", [])
    if not isinstance(candidates_raw, list) or not candidates_raw:
        errors.append(f"{where}: candidates must be a non-empty list")
        candidates_raw = []
    for item in candidates_raw:
        name = item.get("repository") if isinstance(item, dict) else None
        if not isinstance(name, str) or name not in repo_ids:
            errors.append(f"{where}: candidate {name!r} is not in repositories")
            continue
        full_name = name
        if full_name in pool:
            errors.append(f"{where}: candidate {full_name} listed twice")
            continue
        if full_name not in repos:
            continue  # the repository itself is invalid and already reported
        rank = item.get("best_search_rank")
        if rank is not None and (not isinstance(rank, int) or isinstance(rank, bool) or rank < 1):
            errors.append(f"{where}: candidate {full_name} best_search_rank must be >= 1 or null")
            continue
        pool.add(full_name)
        repo = repos[full_name]
        candidates.append(
            RepoData(
                id=repo_ids[full_name],
                full_name=full_name,
                description=repo["description"],
                languages=repo["languages"],
                topics=repo["topics"],
                dependencies=repo["dependencies"],
                has_contributing=repo["has_contributing"],
                has_issue_templates=repo["has_issue_templates"],
                has_good_first_issue_label=repo["has_good_first_issue_label"],
                has_help_wanted_label=repo["has_help_wanted_label"],
                snapshot=repo["snapshot"],
                best_search_rank=rank,
            )
        )

    judgments: dict[str, int] = {}
    judgments_raw = data.get("judgments", {})
    if not isinstance(judgments_raw, dict):
        errors.append(f"{where}: judgments must be an object keyed by full name")
        judgments_raw = {}
    for full_name, grade in judgments_raw.items():
        if full_name not in pool and full_name in repos:
            errors.append(f"{where}: judgment for {full_name}, which is not in the pool")
        elif full_name not in repo_ids:
            errors.append(f"{where}: judgment for unknown repository {full_name}")
        elif grade not in GRADES or isinstance(grade, bool):
            errors.append(f"{where}: judgment for {full_name} must be 0, 1 or 2")
        else:
            judgments[full_name] = grade
    if not any(grade >= 1 for grade in judgments.values()) and len(errors) == before:
        errors.append(f"{where}: needs at least one judgment of 1 or 2")

    if len(errors) > before:
        return None
    pool_ids = {repo.id for repo in candidates}
    return BenchmarkDeveloper(
        id=data["id"],
        description=str(data.get("description", "")),
        features=DeveloperFeatures(skills=skills, interests=interests, experience_level=level),
        candidates=tuple(sorted(candidates, key=lambda r: r.full_name)),
        issues={repo_id: found for repo_id, found in issues.items() if repo_id in pool_ids},
        judgments=judgments,
    )
