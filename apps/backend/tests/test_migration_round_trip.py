"""Every migration reverses and reapplies cleanly (change migration-round-trip)."""

from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from recommendations.models import ScoringConfig

from .shared_fixtures import active_configs

Schema = dict[str, dict[str, Any]]


def schema() -> Schema:
    """Tables, columns (with types) and constraints/indexes (with columns) of the database."""
    snapshot: Schema = {}
    introspection = connection.introspection
    with connection.cursor() as cursor:
        for table in introspection.get_table_list(cursor):
            if table.type != "t":
                continue
            columns = {
                column.name: (column.type_code, column.null_ok)
                for column in introspection.get_table_description(cursor, table.name)
            }
            constraints = {
                name: (
                    tuple(info["columns"] or ()),
                    info["primary_key"],
                    info["unique"],
                    info["foreign_key"],
                    info["check"],
                    info["index"],
                )
                for name, info in introspection.get_constraints(cursor, table.name).items()
            }
            snapshot[table.name] = {"columns": columns, "constraints": constraints}
    return snapshot


SEEDS = {"v1-deterministic", "v2-deterministic"}


@pytest.mark.django_db(transaction=True)
def test_every_migration_reverses_and_reapplies() -> None:
    """Unapply every app to before its first migration, apply all again: the schema and the
    seeded scoring configs come back with one active. An operation without a reverse raises
    ``IrreversibleError`` naming its migration."""
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    zero = [(app, None) for app in sorted(executor.loader.migrated_apps)]
    # Seeds are checked only afterwards: an earlier transactional test may have flushed them.
    before = schema()

    try:
        executor.migrate(zero)
        executor.loader.build_graph()
        assert set(schema()) <= {"django_migrations"}
    finally:
        # A failure part-way must not leave the shared test database without tables for every
        # later test (CR9-4): the reapply below runs either way.
        executor.loader.build_graph()
        executor.migrate(latest)
        executor.loader.build_graph()
    assert executor.migration_plan(latest) == []
    assert schema() == before
    assert set(ScoringConfig.objects.values_list("version", flat=True)) >= SEEDS
    assert len(active_configs()) == 1, active_configs()
