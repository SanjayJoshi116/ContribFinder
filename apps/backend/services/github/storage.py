"""Storing normalized GitHub repository data (shared by the profile sync, discovery and
repository analysis). Callers own the transaction. Rows are never deleted here: a repository
whose name another GitHub ID now has gives the name up (``lifecycle.release_name``)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from django.conf import settings

from repositories.models import (
    Repository,
    RepositoryDependency,
    RepositoryLanguage,
    RepositoryTopic,
)
from services.profiling.manifests import is_manifest, parse_manifest
from services.repositories.lifecycle import release_name

from .client import ContentEntry, GitHubClient, GitHubRepo
from .errors import GitHubNotFound


def upsert_repository(gh: GitHubRepo, now: Any, *, metadata_fetched: bool = True) -> Repository:
    """Store ``gh`` by GitHub ID. ``metadata_fetched=False`` (a search result, which carries
    no languages) updates the fields but not ``synced_at`` of an existing row, so its metadata
    still goes stale on schedule."""
    # Another repository that had this name (renamed away, or deleted and recreated) keeps its
    # row and links; its next analysis finds it by GitHub ID.
    release_name(gh.full_name, gh.github_id)
    fields: dict[str, Any] = {
        "owner_login": gh.owner_login,
        "name": gh.name,
        "full_name": gh.full_name,
        "description": gh.description,
        "html_url": gh.html_url,
        "default_branch": gh.default_branch,
        "stars": gh.stars,
        "forks": gh.forks,
        "open_issues": gh.open_issues,
        "primary_language": gh.primary_language,
        "license_spdx": gh.license_spdx,
        "is_fork": gh.is_fork,
        "is_archived": gh.is_archived,
        "github_created_at": gh.created_at,
        "github_updated_at": gh.updated_at,
        "pushed_at": gh.pushed_at,
    }
    fetched = {"synced_at": now}
    repo, _ = Repository.objects.update_or_create(
        github_id=gh.github_id,
        defaults=fields | fetched if metadata_fetched else fields,
        create_defaults=fields | fetched,
    )
    return repo


def replace_languages(repo: Repository, languages: dict[str, int]) -> None:
    RepositoryLanguage.objects.filter(repository=repo).delete()
    RepositoryLanguage.objects.bulk_create(
        RepositoryLanguage(repository=repo, language=lang, bytes=count)
        for lang, count in languages.items()
    )


def replace_topics(repo_pk: int, topics: Iterable[str]) -> None:
    RepositoryTopic.objects.filter(repository_id=repo_pk).delete()
    RepositoryTopic.objects.bulk_create(
        RepositoryTopic(repository_id=repo_pk, topic=topic) for topic in dict.fromkeys(topics)
    )


def read_manifests(
    client: GitHubClient, full_name: str, entries: Sequence[ContentEntry] | None = None
) -> dict[tuple[str, str], str]:
    """``{(ecosystem, name): manifest path}`` from the repository's root manifests.
    ``entries`` is the root listing when the caller already has it."""
    found: dict[tuple[str, str], str] = {}
    root = client.list_root_contents(full_name) if entries is None else entries
    for entry in root:
        if entry.type != "file" or not is_manifest(entry.name):
            continue
        if entry.size > settings.GITHUB_MANIFEST_MAX_BYTES:
            continue
        try:
            text = client.get_file(full_name, entry.name)
        except GitHubNotFound:
            continue  # removed between listing and fetching
        for dep in parse_manifest(entry.name, text):
            found.setdefault((dep.ecosystem, dep.name), entry.name)
    return found


def replace_dependencies(repo: Repository, dependencies: dict[tuple[str, str], str]) -> None:
    RepositoryDependency.objects.filter(repository=repo).delete()
    RepositoryDependency.objects.bulk_create(
        RepositoryDependency(repository=repo, ecosystem=eco, name=name, manifest_path=path)
        for (eco, name), path in dependencies.items()
    )
