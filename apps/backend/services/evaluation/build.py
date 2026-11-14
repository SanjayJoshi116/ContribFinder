"""Build a benchmark from several datasets and judged exports (spec: recommendation-evaluation
"Benchmark with real developers"; design D3). Pure apart from reading the inputs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .dataset import FORMAT, DatasetError, parse

ERROR = "error"
FIRST = "first"
ON_CONFLICT = (ERROR, FIRST)


class BuildError(Exception):
    pass


def build(
    name: str,
    description: str,
    inputs: Sequence[tuple[str, dict[str, Any]]],
    on_conflict: str = ERROR,
) -> tuple[dict[str, Any], list[str]]:
    """``inputs`` are ``(label, raw dataset)`` in order. Returns the merged dataset and the
    repositories whose differing entries were resolved by taking the first input's."""
    repositories: dict[str, Any] = {}
    origin: dict[str, str] = {}
    developers: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    resolved: dict[str, None] = {}  # ordered, each repository once
    for label, raw in inputs:
        if not isinstance(raw, dict) or raw.get("format") != FORMAT:
            raise BuildError(f"{label} is not a format {FORMAT} dataset.")
        catalog = raw.get("repositories", {})
        if not isinstance(catalog, dict):
            raise BuildError(f"{label}: repositories must be a JSON object.")
        people = raw.get("developers", [])
        if not isinstance(people, list) or not all(isinstance(d, dict) for d in people):
            raise BuildError(f"{label}: developers must be a list of JSON objects.")
        for full_name, entry in catalog.items():
            if full_name not in repositories:
                repositories[full_name], origin[full_name] = entry, label
            elif repositories[full_name] != entry:
                if on_conflict != FIRST:
                    raise BuildError(
                        f"Repository {full_name} differs between {origin[full_name]} and {label}; "
                        "use --on-conflict first to keep the first."
                    )
                resolved[full_name] = None
        for developer in people:
            dev_id = developer.get("id")
            if dev_id in seen:
                raise BuildError(f"Developer {dev_id} appears in {seen[dev_id]} and {label}.")
            seen[dev_id] = label
            developers.append(developer)
    result = {
        "format": FORMAT,
        "name": name,
        "description": description,
        "repositories": repositories,
        "developers": developers,
    }
    try:
        parse(result)
    except DatasetError as exc:
        raise BuildError(str(exc)) from exc
    return result, list(resolved)
