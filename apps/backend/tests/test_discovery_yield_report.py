"""Discovery yield report (change discovery-search-yield, group 2)."""

import json
from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from jobs.models import SyncJob
from services.discovery.yield_report import build

from .factories import UserFactory


def ran(
    source: str, results: int, rejected: dict[str, int], recorded: int, band: str = ""
) -> dict[str, Any]:
    return {
        "source": source,
        "band": band,
        "results": results,
        "rejections": rejected,
        "recorded": recorded,
    }


def queries(*entries: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f"q{i}": e for i, e in enumerate(entries)}


def test_rejections_per_strategy() -> None:
    # Spec: 10 language requests, 300 results, 90 no_license, 150 recorded; 10 interest
    # requests, 200 results, 20 no_license, 170 recorded.
    run = queries(
        *[ran("language_search", 30, {"no_license": 9, "archived": 6}, 15) for _ in range(10)],
        *[ran("interest_search", 20, {"no_license": 2, "inactive": 1}, 17) for _ in range(10)],
    )
    report = build([run])

    language, interest = report.strategies
    assert (language.name, interest.name) == ("language_search", "interest_search")
    assert (language.requests, language.results, language.recorded) == (10, 300, 150)
    assert language.rejections == {"no_license": 90, "archived": 60}
    assert interest.rejections["no_license"] == 20
    assert language.recorded_share == pytest.approx(0.50)
    assert interest.recorded_share == pytest.approx(0.85)
    assert language.results_per_request == pytest.approx(30.0)
    assert report.total.requests == 20 and report.total.rejections["no_license"] == 110


def test_yield_per_band_and_strategy_band() -> None:
    run = queries(
        ran("language_search", 30, {"no_license": 10}, 18, band="20..999"),
        ran("language_search", 30, {"no_license": 2}, 27, band="1000+"),
        ran("skill_search", 10, {}, 10, band="1000+"),
    )
    report = build([run])
    small, large = report.bands
    assert (small.name, large.name) == ("20..999", "1000+")  # by lower star bound
    assert small.recorded_share == pytest.approx(0.6)
    assert large.results_per_request == pytest.approx(20.0)
    assert [row.name for row in report.strategy_bands] == [
        "language_search 20..999",
        "language_search 1000+",
        "skill_search 1000+",
    ]


def test_single_band_reads_all() -> None:
    report = build([queries(ran("topic_search", 5, {}, 5))])
    assert [row.name for row in report.bands] == ["all"]


def test_refused_requests_count_but_have_no_results() -> None:
    run = queries(
        ran("skill_search", 30, {}, 30),
        {"source": "skill_search", "band": "", "refused": True},
    )
    (skill,) = build([run]).strategies
    assert (skill.requests, skill.refused, skill.results) == (2, 1, 30)
    assert skill.results_per_request == pytest.approx(30.0)  # per request that ran


def test_runs_without_yield_enter_no_figure() -> None:
    report = build([None, {}, queries(ran("language_search", 10, {}, 10))])
    assert (report.runs, report.runs_without_yield) == (3, 2)
    assert report.total.requests == 1


def test_no_results_has_no_share() -> None:
    (row,) = build([queries(ran("topic_search", 0, {}, 0))]).strategies
    assert (row.recorded_share, row.results_per_request) == (None, 0.0)


# --- loading and the command ---------------------------------------------------------------


def discovery_job(user, status: str, yields: dict[str, Any] | None, *, days_ago: int = 1) -> None:
    metadata: dict[str, Any] = {"plan": [{"q": "language:Python secret-query"}]}
    if yields is not None:
        metadata["query_yield"] = yields
    SyncJob.objects.create(
        user=user,
        job_type="repository_discovery",
        status=status,
        started_at=timezone.now() - timedelta(days=days_ago),
        metadata=metadata,
    )


def run_command(*args: str) -> str:
    out = StringIO()
    call_command("discovery_report", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_command_reads_finished_runs_only() -> None:
    first, second = UserFactory(), UserFactory()
    discovery_job(first, "COMPLETED", queries(ran("language_search", 30, {"no_license": 9}, 21)))
    discovery_job(second, "FAILED", queries(ran("interest_search", 10, {}, 10)))
    discovery_job(second, "CANCELLED", None)  # finished before yield was recorded
    discovery_job(first, "RUNNING", queries(ran("topic_search", 99, {}, 99)), days_ago=0)

    output = run_command()

    assert "3 finished runs, 1 without per-query yield" in output
    assert "language_search" in output and "interest_search" in output
    assert "topic_search" not in output  # an active run is left out
    assert "no_license 9" in output


@pytest.mark.django_db
def test_command_window() -> None:
    user = UserFactory()
    discovery_job(user, "COMPLETED", queries(ran("language_search", 30, {}, 30)), days_ago=40)
    discovery_job(user, "COMPLETED", queries(ran("skill_search", 30, {}, 30)), days_ago=2)
    output = run_command("--since", "30")
    assert "skill_search" in output and "language_search" not in output
    assert "No recorded search requests." in run_command("--since", "1")


@pytest.mark.django_db
def test_command_rejects_bad_window() -> None:
    with pytest.raises(CommandError):
        run_command("--since", "0")


@pytest.mark.django_db
def test_json_report_is_aggregates_only(tmp_path) -> None:
    user = UserFactory()
    discovery_job(
        user,
        "COMPLETED",
        {"language:python@0": ran("language_search", 30, {"no_license": 9}, 21, band="20..999")},
    )
    before = list(SyncJob.objects.values_list("pk", "metadata", "status"))
    out = tmp_path / "reports" / "discovery.json"

    run_command("--json", str(out))

    raw = out.read_text(encoding="utf-8")
    report = json.loads(raw)
    assert set(report) == {
        "since_days",
        "runs",
        "runs_without_yield",
        "total",
        "strategies",
        "bands",
        "strategy_bands",
    }
    assert report["strategies"][0]["recorded_share"] == 0.7
    # No query text, query key, user or job identifier.
    assert "secret-query" not in raw and "language:python" not in raw
    assert user.username not in raw
    assert not keys(report) & {"user", "user_id", "job", "job_id", "id", "key", "q", "query"}
    assert list(SyncJob.objects.values_list("pk", "metadata", "status")) == before


def keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys(v)}
    return set()
