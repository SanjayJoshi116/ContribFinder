"""Activating a scoring configuration, used only by the ``activate_scoring_config`` command
(spec: recommendation-evaluation "Activating a configuration"; changes
config-activation-loose-ends, design D1, and activation-command-only). The benchmark comparison
never runs inside a web request.

A configuration replaces the active one only when it is an improvement on the selection
benchmark, unless the operator forces it with a reason. Every activation is audited.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.db import transaction

from accounts.models import AuditEvent
from recommendations.models import ScoringConfig
from services import audit
from services.evaluation import baseline
from services.evaluation.dataset import DatasetError, load, selection_dataset
from services.evaluation.runner import (
    ConfigError,
    ConfigSpec,
    Report,
    Verdict,
    compare,
    evaluate,
)
from services.evaluation.runner import stored_config as load_stored_config


class ActivationError(Exception):
    """The request itself is wrong (unknown or invalid version, force without a reason)."""


class ActivationRefused(Exception):
    """The configuration is not an improvement over the active one."""

    def __init__(self, version: str, active: str, failures: tuple[str, ...]) -> None:
        super().__init__(f"{version} is not an improvement over {active}")
        self.failures = failures


@dataclass(frozen=True)
class Activation:
    version: str
    previous: str  # "" when nothing was active
    changed: bool
    forced: bool = False
    failures: tuple[str, ...] = ()


Judge = Callable[[ConfigSpec, ConfigSpec], Verdict]


def benchmark_judge(candidate: ConfigSpec, active: ConfigSpec) -> Verdict:
    """The improvement rule on the selection benchmark, with the pinned baseline defaults, so
    a local .env cannot change the verdict."""
    dataset = load(selection_dataset())

    def report(spec: ConfigSpec) -> Report:
        return evaluate(dataset, spec, min_score=baseline.MIN_SCORE, top_n=baseline.TOP_N)

    return compare(report(active), [report(candidate)])[0]


def activate(
    version: str,
    *,
    force: bool = False,
    reason: str = "",
    judge: Judge | None = None,
) -> Activation:
    """``judge`` defaults to ``benchmark_judge`` (looked up at call time)."""
    try:
        candidate = load_stored_config(version)
    except ConfigError as exc:
        raise ActivationError(str(exc)) from exc
    active = ScoringConfig.objects.filter(is_active=True).first()
    if active is not None and active.version == version:
        return Activation(version, version, changed=False)
    reason = reason.strip()
    if force and not reason:
        raise ActivationError("A forced activation needs a reason.")

    failures: tuple[str, ...] = ()
    if active is not None:
        try:
            verdict = (judge or benchmark_judge)(candidate, load_stored_config(active.version))
        except (ConfigError, DatasetError) as exc:
            # A broken benchmark or active config must not block a forced rollback.
            if not force:
                raise ActivationError(f"Cannot compare with {active.version}: {exc}") from exc
            failures = (f"not compared: {exc}",)
        else:
            failures = verdict.failures
            if verdict.improvement:
                force = False  # the rule was met; nothing was overridden
            elif not force:
                raise ActivationRefused(version, active.version, failures)

    previous = active.version if active is not None else ""
    with transaction.atomic():
        # Lock every row in pk order, so two activations cannot interleave or deadlock.
        list(ScoringConfig.objects.select_for_update().order_by("pk").values_list("pk"))
        # The verdict holds only against the config it was judged against.
        now_active = (
            ScoringConfig.objects.filter(is_active=True).values_list("version", flat=True).first()
        )
        if now_active == version:
            return Activation(version, version, changed=False)
        if (now_active or "") != previous:
            raise ActivationError(
                f"The active configuration changed to {now_active or 'none'} meanwhile; try again."
            )
        ScoringConfig.objects.filter(is_active=True).exclude(version=version).update(
            is_active=False
        )
        ScoringConfig.objects.filter(version=version).update(is_active=True)
        audit.record(
            AuditEvent.Action.SCORING_CONFIG_ACTIVATED,
            AuditEvent.Outcome.SUCCESS,
            metadata={
                "config_version": version,
                "previous_version": previous,
                "forced": force,
                "reason": reason,
                "failures": list(failures),
                "via": "command",  # entries from the former admin action say "admin"
            },
        )
    return Activation(version, previous, changed=True, forced=force, failures=failures)
