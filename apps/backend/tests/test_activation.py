"""Activating a scoring configuration (spec recommendation-evaluation, "Activating a
configuration"; change config-activation-loose-ends, design D1)."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import reverse

from accounts.models import AuditEvent
from recommendations.models import ScoringConfig
from services.evaluation import baseline, metrics
from services.evaluation.dataset import DatasetError
from services.evaluation.runner import ConfigSpec, Verdict
from services.ranking import activation
from services.ranking.activation import ActivationError, ActivationRefused, activate
from services.ranking.config import V2_PARAMS, V2_WEIGHTS

from .shared_fixtures import active_configs as active

pytestmark = pytest.mark.django_db

FAILURES = ("ndcg@10 0.5000 is not higher than 0.6000",)


def judge(improvement: bool):
    calls: list[tuple[str, str]] = []

    def fake(candidate: ConfigSpec, active: ConfigSpec) -> Verdict:
        calls.append((candidate.label, active.label))
        return Verdict(candidate.label, improvement, () if improvement else FAILURES)

    fake.calls = calls  # type: ignore[attr-defined]
    return fake


def events() -> list[AuditEvent]:
    return list(AuditEvent.objects.filter(action=AuditEvent.Action.SCORING_CONFIG_ACTIVATED))


def test_improvement_is_activated_and_audited() -> None:
    fake = judge(True)
    result = activate("v1-deterministic", via="command", judge=fake)

    assert active() == ["v1-deterministic"]
    assert fake.calls == [("v1-deterministic", "v2-deterministic")]
    assert (result.changed, result.previous, result.forced) == (True, "v2-deterministic", False)
    (event,) = events()
    assert event.outcome == AuditEvent.Outcome.SUCCESS
    assert event.metadata == {
        "config_version": "v1-deterministic",
        "previous_version": "v2-deterministic",
        "forced": False,
        "reason": "",
        "failures": [],
        "via": "command",
    }


def test_refusal_changes_nothing() -> None:
    with pytest.raises(ActivationRefused) as refused:
        activate("v1-deterministic", via="command", judge=judge(False))

    assert refused.value.failures == FAILURES
    assert active() == ["v2-deterministic"]
    assert events() == []


@pytest.mark.parametrize("reason", ["", "   "])
def test_force_needs_a_reason_before_evaluating(reason: str) -> None:
    fake = judge(False)
    with pytest.raises(ActivationError, match="reason"):
        activate("v1-deterministic", force=True, reason=reason, via="command", judge=fake)

    assert fake.calls == []
    assert active() == ["v2-deterministic"]


def test_forced_activation_records_reason_and_failures() -> None:
    result = activate(
        "v1-deterministic",
        force=True,
        reason=" rollback after incident ",
        via="command",
        judge=judge(False),
    )

    assert active() == ["v1-deterministic"]
    assert (result.forced, result.failures) == (True, FAILURES)
    (event,) = events()
    assert event.metadata["forced"] is True
    assert event.metadata["reason"] == "rollback after incident"
    assert event.metadata["failures"] == list(FAILURES)


def test_forced_improvement_is_not_recorded_as_forced() -> None:
    result = activate("v1-deterministic", force=True, reason="x", via="command", judge=judge(True))

    assert result.forced is False
    assert events()[0].metadata["forced"] is False


def test_broken_benchmark_refuses_unless_forced() -> None:
    def broken(candidate: ConfigSpec, active: ConfigSpec) -> Verdict:
        raise DatasetError(["not JSON"])

    with pytest.raises(ActivationError, match="not JSON"):
        activate("v1-deterministic", via="command", judge=broken)
    assert active() == ["v2-deterministic"]

    result = activate(
        "v1-deterministic", force=True, reason="rollback", via="command", judge=broken
    )
    assert active() == ["v1-deterministic"]
    assert result.forced is True
    assert "not JSON" in result.failures[0]


def test_broken_active_config_does_not_block_forced_rollback() -> None:
    ScoringConfig.objects.filter(version="v2-deterministic").update(
        weights={**V2_WEIGHTS, "skill": -1.0}
    )
    with pytest.raises(ActivationError, match="v2-deterministic"):
        activate("v1-deterministic", via="command", judge=judge(True))

    activate("v1-deterministic", force=True, reason="rollback", via="command", judge=judge(True))
    assert active() == ["v1-deterministic"]


def test_active_changed_after_judging_is_refused() -> None:
    def racing(candidate: ConfigSpec, current: ConfigSpec) -> Verdict:
        # Another activation commits while this one is being judged.
        ScoringConfig.objects.update(is_active=False)
        ScoringConfig.objects.create(version="v3-other", weights=V2_WEIGHTS, params=V2_PARAMS)
        ScoringConfig.objects.filter(version="v3-other").update(is_active=True)
        return Verdict(candidate.label, True, ())

    with pytest.raises(ActivationError, match="v3-other"):
        activate("v1-deterministic", via="command", judge=racing)
    assert active() == ["v3-other"]
    assert events() == []


@override_settings(RECOMMENDATION_MIN_SCORE=0.9, RECOMMENDATIONS_TOP_N=3)
def test_benchmark_judge_ignores_local_settings(monkeypatch) -> None:
    seen: list[tuple[float, int]] = []

    def fake_evaluate(dataset, spec, *, min_score, top_n):
        seen.append((min_score, top_n))
        return spec.label

    monkeypatch.setattr(activation, "evaluate", fake_evaluate)
    monkeypatch.setattr(activation, "compare", lambda base, others: [Verdict("x", True, ())])
    activation.benchmark_judge(ConfigSpec("a", {}, {}), ConfigSpec("b", {}, {}))

    assert seen == [(baseline.MIN_SCORE, baseline.TOP_N)] * 2


def test_unknown_version_is_refused() -> None:
    with pytest.raises(ActivationError, match="v9-missing"):
        activate("v9-missing", via="command", judge=judge(True))
    assert active() == ["v2-deterministic"]


def test_invalid_stored_configuration_is_refused() -> None:
    ScoringConfig.objects.create(
        version="broken", weights={**V2_WEIGHTS, "skill": -1.0}, params=V2_PARAMS
    )
    with pytest.raises(ActivationError, match="invalid"):
        activate("broken", via="command", judge=judge(True))
    assert active() == ["v2-deterministic"]


def test_already_active_changes_and_records_nothing() -> None:
    fake = judge(True)
    result = activate("v2-deterministic", via="command", judge=fake)

    assert result.changed is False
    assert fake.calls == []
    assert events() == []
    assert active() == ["v2-deterministic"]


def test_nothing_active_activates_without_comparing() -> None:
    ScoringConfig.objects.update(is_active=False)
    fake = judge(False)

    result = activate("v1-deterministic", via="command", judge=fake)

    assert fake.calls == []
    assert active() == ["v1-deterministic"]
    assert result.previous == ""


@override_settings(
    RECOMMENDATION_MIN_SCORE=baseline.MIN_SCORE, RECOMMENDATIONS_TOP_N=baseline.TOP_N
)
def test_benchmark_judge_refuses_v1_over_v2() -> None:
    """The real rule on the selection benchmark (benchmark-v1 until benchmark-v2 holds a real
    developer): v1 has a lower NDCG@10 than v2 (baselines.json)."""
    with pytest.raises(ActivationRefused) as refused:
        activate("v1-deterministic", via="command")

    assert any(failure.startswith(metrics.PRIMARY) for failure in refused.value.failures)
    assert active() == ["v2-deterministic"]


# Command and admin (design D2, D3): thin wrappers around the service.


@pytest.fixture
def fake_judge(monkeypatch):
    """Make the default judge return a fixed verdict; set ``.improvement`` per test."""

    class State:
        improvement = False

    def fake(candidate: ConfigSpec, active: ConfigSpec) -> Verdict:
        ok = State.improvement
        return Verdict(candidate.label, ok, () if ok else FAILURES)

    monkeypatch.setattr(activation, "benchmark_judge", fake)
    return State


def run_command(*args: str) -> str:
    out = StringIO()
    call_command("activate_scoring_config", *args, stdout=out)
    return out.getvalue()


def test_command_activates_an_improvement(fake_judge) -> None:
    fake_judge.improvement = True
    output = run_command("v1-deterministic")

    assert "v1-deterministic is active, replacing v2-deterministic" in output
    assert active() == ["v1-deterministic"]
    assert events()[0].metadata["via"] == "command"


def test_command_refusal_lists_failures_and_fails(fake_judge) -> None:
    out = StringIO()
    with pytest.raises(CommandError, match="--force --reason"):
        call_command("activate_scoring_config", "v1-deterministic", stdout=out)

    assert FAILURES[0] in out.getvalue()
    assert active() == ["v2-deterministic"]


def test_command_force_without_reason_fails(fake_judge) -> None:
    with pytest.raises(CommandError, match="reason"):
        run_command("v1-deterministic", "--force")
    assert active() == ["v2-deterministic"]


def test_command_forced_with_reason(fake_judge) -> None:
    output = run_command("v1-deterministic", "--force", "--reason", "rollback")

    assert "(forced)" in output and FAILURES[0] in output
    assert active() == ["v1-deterministic"]


def test_command_already_active(fake_judge) -> None:
    assert "already active" in run_command("v2-deterministic")
    assert events() == []


def test_admin_action_refuses_and_points_to_the_command(fake_judge, admin_client) -> None:
    v1 = ScoringConfig.objects.get(version="v1-deterministic")
    response = admin_client.post(
        reverse("admin:recommendations_scoringconfig_changelist"),
        {"action": "activate", "_selected_action": [v1.pk]},
        follow=True,
    )

    text = response.content.decode()
    assert "was not activated" in text and FAILURES[0] in text and "--force" in text
    assert active() == ["v2-deterministic"]
    assert events() == []


def test_admin_action_activates_an_improvement_with_the_user(
    fake_judge, admin_client, admin_user
) -> None:
    fake_judge.improvement = True
    v1 = ScoringConfig.objects.get(version="v1-deterministic")
    admin_client.post(
        reverse("admin:recommendations_scoringconfig_changelist"),
        {"action": "activate", "_selected_action": [v1.pk]},
    )

    assert active() == ["v1-deterministic"]
    (event,) = events()
    assert (event.user_id, event.metadata["via"]) == (admin_user.pk, "admin")
