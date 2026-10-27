"""Seeding helpers for scoring configurations after ``v2-deterministic``.

Django's migration loader skips modules whose name starts with ``_``, so this is not a
migration. It is frozen like one: applied migrations call these functions, so changing what they
do means adding a new function, never editing these. They read only the historical ``apps``,
never settings or ``services``.

A later seed stores its version inactive and leaves activation to the operator
(``activate_scoring_config``, benchmark-gated and audited); its reversal never re-activates
anything (recommendation-engine, "Versioned scoring configuration")::

    def seed(apps, schema_editor):
        store_inactive(apps, version=VERSION, description=DESCRIPTION, weights=WEIGHTS,
                       params=PARAMS)

    def unseed(apps, schema_editor):
        remove_unused(apps, version=VERSION)
"""

from typing import Any

from django.db.migrations.state import StateApps


def store_inactive(
    apps: StateApps,
    *,
    version: str,
    description: str,
    weights: dict[str, float],
    params: dict[str, Any],
) -> None:
    """Store ``version`` inactive. An already stored version is left exactly as it is (values
    and activation): a re-apply after a rollback that kept it, or after the operator activated
    it, changes nothing."""
    ScoringConfig = apps.get_model("recommendations", "ScoringConfig")
    if ScoringConfig.objects.filter(version=version).exists():
        return
    ScoringConfig.objects.create(
        version=version, description=description, weights=weights, params=params, is_active=False
    )


def remove_unused(apps: StateApps, *, version: str) -> None:
    """Delete ``version`` only when it is inactive and produced no recommendations. An active
    version stays (deleting it would leave none active, and choosing a successor is the
    operator's call); one with recommendations is protected anyway."""
    ScoringConfig = apps.get_model("recommendations", "ScoringConfig")
    ScoringConfig.objects.filter(
        version=version, is_active=False, recommendations__isnull=True
    ).delete()
