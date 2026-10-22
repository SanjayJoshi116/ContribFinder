"""Scoring-config seed migrations in both directions (change dev-scripts-checks, H-10, H-11)."""

import importlib

import pytest
from django.apps import apps as global_apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from developers.models import DeveloperProfile
from e2e.builders import make_candidate_repo
from recommendations.models import ScoringConfig
from services.ranking.config import V2_PARAMS, V2_WEIGHTS

from .test_models_phase5 import make_recommendation

seed_v1 = importlib.import_module("recommendations.migrations.0002_seed_v1_deterministic")
seed_v2 = importlib.import_module("recommendations.migrations.0003_seed_v2_deterministic")


def run(migration, direction: str) -> None:
    getattr(migration, direction)(global_apps, None)


def active() -> list[str]:
    return list(ScoringConfig.objects.filter(is_active=True).values_list("version", flat=True))


def assert_one_active_if_any() -> None:
    if ScoringConfig.objects.exists():
        assert len(active()) == 1, active()


ROLLBACK_AND_REAPPLY = [
    (seed_v2, "unseed"),
    (seed_v1, "unseed"),
    (seed_v1, "seed"),
    (seed_v2, "seed"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("recommendations_on", [None, "v1-deterministic", "v2-deterministic"])
def test_reverse_and_reapply_keeps_one_active(user, recommendations_on: str | None) -> None:
    """A config with recommendations survives its unseed; one stays active after every step."""
    if recommendations_on:
        profile = DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())
        config = ScoringConfig.objects.get(version=recommendations_on)
        make_recommendation(profile, make_candidate_repo(1), config=config)

    for migration, direction in ROLLBACK_AND_REAPPLY:
        run(migration, direction)
        assert_one_active_if_any()

    assert active() == ["v2-deterministic"]


@pytest.mark.django_db
def test_v1_unseed_deletes_v1_when_nothing_else_is_stored() -> None:
    run(seed_v2, "unseed")
    ScoringConfig.objects.exclude(version="v1-deterministic").delete()

    run(seed_v1, "unseed")

    assert not ScoringConfig.objects.exists()


@pytest.mark.django_db
def test_reapplying_v1_after_rollback_keeps_v1_active() -> None:
    """H-11: the rollback re-activates v1; re-seeding must not count v1 against itself."""
    run(seed_v2, "unseed")
    ScoringConfig.objects.filter(version="v2-deterministic").delete()
    assert active() == ["v1-deterministic"]

    run(seed_v1, "seed")

    assert active() == ["v1-deterministic"]


@pytest.mark.django_db
def test_operator_config_stays_active_through_v2_seed() -> None:
    """H-10: v2 replaces only an earlier seed, never an operator's choice."""
    ScoringConfig.objects.update(is_active=False)
    ScoringConfig.objects.filter(version="v2-deterministic").delete()
    ScoringConfig.objects.create(
        version="operator-choice", weights=V2_WEIGHTS, params=V2_PARAMS, is_active=True
    )

    run(seed_v2, "seed")

    assert active() == ["operator-choice"]
    assert not ScoringConfig.objects.get(version="v2-deterministic").is_active


@pytest.mark.django_db
def test_v2_seed_replaces_v1() -> None:
    ScoringConfig.objects.update(is_active=False)
    ScoringConfig.objects.filter(version="v1-deterministic").update(is_active=True)

    run(seed_v2, "seed")

    assert active() == ["v2-deterministic"]


@pytest.mark.django_db(transaction=True)
def test_real_migrations_round_trip() -> None:
    """The migration graph itself: back before both seeds and forward again."""
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes("recommendations")
    executor.migrate([("recommendations", "0001_initial")])
    executor.loader.build_graph()
    executor.migrate(latest)

    assert active() == ["v2-deterministic"]
