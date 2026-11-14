"""Building benchmarks from judged exports, and the selection dataset (benchmark-real-judgments,
group 3)."""

import copy
import json
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from services.evaluation.build import BuildError, build
from services.evaluation.dataset import DEFAULT_DATASET, parse, selection_dataset

from .test_evaluation_dataset import minimal


def real(dev_id: str) -> dict[str, Any]:
    raw = minimal()
    developer = raw["developers"][0]
    developer |= {"id": dev_id, "kind": "real", "judgments": {"bench/django-kit": 1}}
    return raw


def test_build_two_inputs() -> None:
    result, resolved = build("b", "", [("personas", minimal()), ("real-a", real("real-a"))])
    dataset = parse(result)
    assert [(d.id, d.kind) for d in dataset.developers] == [
        ("dev-a", "persona"),
        ("real-a", "real"),
    ]
    assert dataset.repository_count == 2 and resolved == []


def test_duplicate_developer() -> None:
    with pytest.raises(BuildError, match="Developer dev-a appears in a and b"):
        build("b", "", [("a", minimal()), ("b", minimal())])


def test_conflicting_repository() -> None:
    other = real("real-a")
    other["repositories"]["bench/django-kit"]["snapshot"]["days_since_push"] = 40
    with pytest.raises(BuildError, match="Repository bench/django-kit differs between a and b"):
        build("b", "", [("a", minimal()), ("b", other)])
    result, resolved = build("b", "", [("a", minimal()), ("b", other)], on_conflict="first")
    assert resolved == ["bench/django-kit"]
    assert result["repositories"]["bench/django-kit"]["snapshot"]["days_since_push"] == 2


def test_repository_resolved_by_choice_is_listed_once() -> None:
    inputs = [("a", minimal())]
    for index, days in enumerate((40, 50), start=1):
        other = real(f"real-{index}")
        other["repositories"]["bench/django-kit"]["snapshot"]["days_since_push"] = days
        inputs.append((f"r{index}", other))
    _, resolved = build("b", "", inputs, on_conflict="first")
    assert resolved == ["bench/django-kit"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"repositories": []}, "bad: repositories must be a JSON object"),
        ({"developers": ["dev-x"]}, "bad: developers must be a list of JSON objects"),
        ({"developers": {"id": "dev-x"}}, "bad: developers must be a list of JSON objects"),
    ],
    ids=["repositories-list", "developer-string", "developers-object"],
)
def test_badly_shaped_input(change: dict[str, Any], message: str) -> None:
    with pytest.raises(BuildError, match=message):
        build("b", "", [("a", minimal()), ("bad", real("real-a") | change)])


def test_input_not_a_dataset(tmp_path) -> None:
    with pytest.raises(BuildError, match=r"report\.json is not a format 1 dataset"):
        build("b", "", [("a", minimal()), ("report.json", [])])  # type: ignore[list-item]
    with pytest.raises(BuildError, match=r"old\.json is not a format 1 dataset"):
        build("b", "", [("a", minimal()), ("old.json", minimal() | {"format": 0})])

    a, report, out = tmp_path / "a.json", tmp_path / "report.json", tmp_path / "out.json"
    a.write_text(json.dumps(minimal()), encoding="utf-8")
    report.write_text(json.dumps([{"config": "v2"}]), encoding="utf-8")
    with pytest.raises(CommandError, match=f"{report.name} is not a format 1 dataset"):
        call_command(
            "build_benchmark", "--name", "x", "--out", str(out), "--input", str(a),
            "--input", str(report),
        )  # fmt: skip
    assert not out.exists()


def test_build_command(tmp_path) -> None:
    a, b, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "out.json"
    a.write_text(json.dumps(minimal()), encoding="utf-8")
    b.write_text(json.dumps(real("real-a")), encoding="utf-8")
    stdout = StringIO()
    call_command(
        "build_benchmark",
        "--name",
        "bench-x",
        "--out",
        str(out),
        "--input",
        str(a),
        "--input",
        str(b),
        stdout=stdout,
    )
    assert "1 persona, 1 real developers, 2 repositories" in stdout.getvalue()
    assert parse(json.loads(out.read_text(encoding="utf-8"))).name == "bench-x"


def test_selection_dataset(tmp_path) -> None:
    candidate = tmp_path / "benchmark-v2.json"
    assert selection_dataset(candidate) == DEFAULT_DATASET  # missing
    personas_only = copy.deepcopy(minimal())
    candidate.write_text(json.dumps(personas_only), encoding="utf-8")
    assert selection_dataset(candidate) == DEFAULT_DATASET  # no real developer
    candidate.write_text(json.dumps(real("real-a")), encoding="utf-8")
    assert selection_dataset(candidate) == candidate
