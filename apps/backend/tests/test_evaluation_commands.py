"""evaluate_ranking and export_benchmark_developer commands (Phase 8b, group 5)."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from recommendations.models import Recommendation, ScoringConfig
from services.evaluation.dataset import DatasetError, parse
from services.ranking.config import V2_PARAMS, V2_WEIGHTS

from .test_evaluation_dataset import minimal
from .test_issue_matching import django_issues
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    pool,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]


@pytest.fixture
def dataset_path(tmp_path):
    path = tmp_path / "mini.json"
    path.write_text(json.dumps(minimal()), encoding="utf-8")
    return path


def run(*args: str) -> str:
    out = StringIO()
    call_command("evaluate_ranking", *args, stdout=out)
    return out.getvalue()


def rows() -> list[tuple[str, bool, dict[str, float]]]:
    return list(ScoringConfig.objects.order_by("pk").values_list("version", "is_active", "weights"))


def test_compare_two_stored_versions(dataset_path) -> None:
    before = rows()
    output = run(
        "--dataset",
        str(dataset_path),
        "--config",
        "v1-deterministic",
        "--config",
        "v2-deterministic",
    )
    assert "Dataset mini: 1 developers" in output
    lines = output.splitlines()
    assert any(line.startswith("v1-deterministic ") for line in lines)
    v2 = next(line for line in lines if line.startswith("v2-deterministic "))
    assert "(+0.0000)" in v2  # delta column against the baseline
    assert " 1. bench/django-kit [2]" in output
    assert "v2-deterministic: not an improvement over v1-deterministic" in output
    assert rows() == before and not Recommendation.objects.exists()


def test_default_is_the_active_config(dataset_path) -> None:
    assert "v2-deterministic" in run("--dataset", str(dataset_path))


def test_unknown_version_evaluates_nothing(dataset_path) -> None:
    out = StringIO()
    with pytest.raises(CommandError, match="Unknown scoring configuration version: v9"):
        call_command(
            "evaluate_ranking", "--dataset", str(dataset_path), "--config", "v9", stdout=out
        )
    assert out.getvalue() == ""


def test_invalid_config_file(dataset_path, tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"weights": {"skill": 1.0}, "params": V2_PARAMS}), encoding="utf-8")
    with pytest.raises(CommandError, match="is invalid"):
        run("--dataset", str(dataset_path), "--config-file", str(bad))


def test_unsaved_config_file(dataset_path, tmp_path) -> None:
    good = tmp_path / "candidate.json"
    good.write_text(json.dumps({"weights": V2_WEIGHTS, "params": V2_PARAMS}), encoding="utf-8")
    output = run("--dataset", str(dataset_path), "--config-file", str(good))
    assert str(good) in output
    assert not ScoringConfig.objects.filter(version=str(good)).exists()


def test_invalid_dataset(tmp_path) -> None:
    path = tmp_path / "bad.json"
    raw = minimal()
    raw["developers"][0]["judgments"] = {}
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(CommandError, match="needs at least one judgment"):
        run("--dataset", str(path))


def test_require_improvement_exit_codes(dataset_path, tmp_path) -> None:
    args = ["--dataset", str(dataset_path), "--config", "v2-deterministic"]
    with pytest.raises(CommandError, match="needs at least two"):
        run(*args, "--require-improvement")
    with pytest.raises(CommandError, match="Not every configuration improves"):
        run(*args, "--config", "v2-deterministic", "--require-improvement")  # a tie


def test_require_improvement_passes(tmp_path) -> None:
    # Two relevant repositories; v1 ranks the active but weaker match first, a skill-only
    # configuration puts the highly relevant one first.
    raw = minimal()
    raw["repositories"]["bench/flask-kit"] = {
        "description": "Busy Python service",
        "languages": [["Python", 1000]],
        "has_contributing": True,
        "has_good_first_issue_label": True,
        "has_help_wanted_label": True,
        "has_issue_templates": True,
        "snapshot": {"activity_label": "recently_active", "days_since_push": 1},
    }
    raw["repositories"]["bench/django-kit"]["snapshot"]["activity_label"] = "low_activity"
    raw["repositories"]["bench/django-kit"]["has_contributing"] = False
    raw["developers"][0]["candidates"].append({"repository": "bench/flask-kit"})
    raw["developers"][0]["judgments"]["bench/flask-kit"] = 1
    data = tmp_path / "d.json"
    data.write_text(json.dumps(raw), encoding="utf-8")
    skill_only = tmp_path / "skill.json"
    weights = {name: 0.0 for name in V2_WEIGHTS} | {"skill": 0.5, "framework": 0.5}
    skill_only.write_text(json.dumps({"weights": weights, "params": V2_PARAMS}), encoding="utf-8")

    weak = tmp_path / "activity.json"
    weak_weights = {name: 0.0 for name in V2_WEIGHTS} | {
        "language": 0.4,
        "activity": 0.3,
        "openness": 0.3,
    }
    weak.write_text(json.dumps({"weights": weak_weights, "params": V2_PARAMS}), encoding="utf-8")

    output = run(
        "--dataset",
        str(data),
        "--config-file",
        str(weak),
        "--config-file",
        str(skill_only),
        "--require-improvement",
    )
    assert f"{skill_only}: improvement over {weak}" in output


def test_json_report(dataset_path, tmp_path) -> None:
    out = tmp_path / "report.json"
    run("--dataset", str(dataset_path), "--json", str(out))
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["reports"][0]["config"] == "v2-deterministic"
    assert report["reports"][0]["developers"][0]["top10"][0]["judgment"] == 2


# --- export ---------------------------------------------------------------------------------


def walk(value, keys=None, strings=None, numbers=None):
    """Every object key, string value and number in a JSON value. Language byte counts are
    numbers too, so the GitHub id is checked against numbers that are not language sizes."""
    keys = set() if keys is None else keys
    strings = [] if strings is None else strings
    numbers = set() if numbers is None else numbers
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(key)
            if key != "languages":
                walk(item, keys, strings, numbers)
    elif isinstance(value, list):
        for item in value:
            walk(item, keys, strings, numbers)
    elif isinstance(value, str):
        strings.append(value)
    elif isinstance(value, int | float) and not isinstance(value, bool):
        numbers.add(value)
    return keys, strings, numbers


def test_export_is_anonymized_and_unjudged(user, developer, pool, tmp_path) -> None:  # noqa: F811
    django_issues(pool["django"], count=1)
    out = tmp_path / "dev-f.json"
    call_command(
        "export_benchmark_developer",
        "--user-id",
        str(user.pk),
        "--as",
        "dev-f",
        "--out",
        str(out),
        stdout=StringIO(),
    )
    text = out.read_text(encoding="utf-8")
    data = json.loads(text)
    account = user.github_account
    keys, strings, numbers = walk(data)
    assert not keys & {"username", "email", "github_id", "avatar_url", "token", "user"}
    for secret in (account.username, user.email, user.username, account.access_token_encrypted):
        if secret:
            assert not any(secret in value for value in strings)
    assert account.github_id not in numbers
    (dev,) = data["developers"]
    assert dev["id"] == "dev-f" and dev["judgments"] == {}
    assert set(dev["skills"]) == {"python", "django"}
    assert dev["interests"] == {"developer-tooling": 0.7}
    assert sorted(c["repository"] for c in dev["candidates"]) == sorted(
        r.full_name for r in pool.values()
    )
    assert data["repositories"]["encode/django-tool"]["issues"][0]["technologies"] == ["django"]

    with pytest.raises(DatasetError, match="needs at least one judgment"):
        parse(data)
    dev["judgments"] = {"encode/django-tool": 2}
    assert parse(data).developers[0].id == "dev-f"


def test_export_without_profile(user, tmp_path) -> None:
    out = tmp_path / "none.json"
    with pytest.raises(CommandError, match="no analyzed developer profile"):
        call_command(
            "export_benchmark_developer", "--user-id", str(user.pk), "--as", "x", "--out", str(out)
        )
    assert not out.exists()
