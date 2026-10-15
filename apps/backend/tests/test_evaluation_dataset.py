"""Benchmark dataset loading and validation (Phase 8b, group 3)."""

import copy
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from services.evaluation.dataset import DatasetError, load, parse


def minimal() -> dict[str, Any]:
    return {
        "format": 1,
        "name": "mini",
        "description": "test",
        "repositories": {
            "bench/django-kit": {
                "description": "Django forms toolkit",
                "languages": [["Python", 1000]],
                "topics": ["django"],
                "dependencies": [["pypi", "django"]],
                "has_contributing": True,
                "snapshot": {
                    "activity_label": "recently_active",
                    "days_since_push": 2,
                    "commits_90d": 30,
                    "prs_merged_90d": 5,
                    "contributors": 12,
                },
                "issues": [
                    {
                        "number": 7,
                        "labels": ["good_first_issue"],
                        "contribution_type": "documentation",
                        "difficulty": "beginner",
                        "technologies": ["django"],
                        "updated_at": "2026-09-01T00:00:00+00:00",
                    }
                ],
            },
            "bench/go-proxy": {"languages": [["Go", 500]], "snapshot": None},
        },
        "developers": [
            {
                "id": "dev-a",
                "description": "Django developer",
                "experience_level": "intermediate",
                "skills": {
                    "python": {"confidence": 0.9, "category": "language", "repo_count": 5},
                    "django": {"confidence": 0.7, "repo_count": 3},
                },
                "interests": {"web-development": 0.5},
                "candidates": [
                    {"repository": "bench/go-proxy", "best_search_rank": None},
                    {"repository": "bench/django-kit", "best_search_rank": 2},
                ],
                "judgments": {"bench/django-kit": 2},
            }
        ],
    }


def errors_of(raw: dict[str, Any]) -> list[str]:
    with pytest.raises(DatasetError) as info:
        parse(raw)
    return info.value.errors


def test_minimal_dataset_converts() -> None:
    dataset = parse(minimal())
    assert dataset.name == "mini" and dataset.repository_count == 2
    (dev,) = dataset.developers
    assert dev.features.experience_level == "intermediate"
    assert dev.features.skills["django"].name == "Django"
    assert dev.features.skills["django"].category == "framework"  # from the catalog
    assert dev.features.interests["web-development"][1] == 0.5
    assert [r.full_name for r in dev.candidates] == ["bench/django-kit", "bench/go-proxy"]
    kit = dev.candidates[0]
    assert kit.best_search_rank == 2 and kit.snapshot and kit.snapshot.contributors == 12
    assert kit.dependencies == (("pypi", "django"),)
    (issue,) = dev.issues[kit.id]
    assert issue.number == 7 and issue.technologies == ("django",)
    assert issue.updated_at == datetime(2026, 9, 1, tzinfo=UTC)
    assert dev.candidates[1].snapshot is None


def test_unjudged_candidates_are_allowed() -> None:
    (dev,) = parse(minimal()).developers
    assert "bench/go-proxy" not in dev.judgments


def test_load_reads_a_file(tmp_path) -> None:
    path = tmp_path / "d.json"
    path.write_text(json.dumps(minimal()), encoding="utf-8")
    assert load(path).name == "mini"


def test_unreadable_file(tmp_path) -> None:
    with pytest.raises(DatasetError):
        load(tmp_path / "missing.json")


def test_unknown_format() -> None:
    raw = minimal()
    raw["format"] = 2
    assert errors_of(raw) == ["format: unknown format version 2"]


def test_duplicate_developer_id() -> None:
    raw = minimal()
    raw["developers"].append(copy.deepcopy(raw["developers"][0]))
    assert errors_of(raw) == ["developer dev-a: duplicate id"]


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("skills", "python", "confidence"), 1.5, "skill python confidence must be within 0..1"),
        (("interests", "web-development"), -0.1, "web-development strength must be within 0..1"),
        (("judgments", "bench/django-kit"), 3, "judgment for bench/django-kit must be 0, 1 or 2"),
        (("experience_level",), "guru", "unknown experience_level 'guru'"),
    ],
)
def test_out_of_range_values(path: tuple[str, ...], value: Any, message: str) -> None:
    raw = minimal()
    target = raw["developers"][0]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert any(message in e and "developer dev-a" in e for e in errors_of(raw))


def test_unknown_issue_difficulty_and_technology() -> None:
    raw = minimal()
    issue = raw["repositories"]["bench/django-kit"]["issues"][0]
    issue["difficulty"] = "trivial"
    issue["technologies"] = ["cobol-on-cogs"]
    errors = errors_of(raw)
    assert any("unknown difficulty 'trivial'" in e for e in errors)
    assert any("unknown technology 'cobol-on-cogs'" in e for e in errors)


def test_unknown_skill_and_interest() -> None:
    raw = minimal()
    raw["developers"][0]["skills"]["not-a-skill"] = {"confidence": 0.5}
    raw["developers"][0]["interests"]["not-an-interest"] = 0.5
    errors = errors_of(raw)
    assert "developer dev-a: unknown skill 'not-a-skill'" in errors
    assert "developer dev-a: unknown interest 'not-an-interest'" in errors


def test_judgment_outside_the_pool() -> None:
    raw = minimal()
    raw["developers"][0]["candidates"] = [{"repository": "bench/django-kit"}]
    raw["developers"][0]["judgments"]["bench/go-proxy"] = 1
    assert errors_of(raw) == [
        "developer dev-a: judgment for bench/go-proxy, which is not in the pool"
    ]


def test_no_relevant_judgment() -> None:
    raw = minimal()
    raw["developers"][0]["judgments"] = {"bench/django-kit": 0}
    assert errors_of(raw) == ["developer dev-a: needs at least one judgment of 1 or 2"]


def test_all_errors_are_collected() -> None:
    raw = minimal()
    raw["developers"][0]["skills"]["python"]["confidence"] = 2
    raw["repositories"]["bench/go-proxy"]["snapshot"] = {"activity_label": "busy"}
    assert len(errors_of(raw)) == 2


def test_kind_defaults_to_persona_and_is_validated() -> None:
    raw = minimal()
    assert parse(raw).developers[0].kind == "persona"
    raw["developers"][0]["kind"] = "real"
    assert parse(raw).developers[0].kind == "real"
    raw["developers"][0]["kind"] = "robot"
    assert errors_of(raw) == ["developer dev-a: kind must be one of persona, real"]
