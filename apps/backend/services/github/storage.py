"""Storing normalized GitHub repository data (shared by the profile sync and Phase 4
repository analysis). Callers own the transaction."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.conf import settings

from repositories.models import (
    Repository,
    RepositoryDependency,
    RepositoryLanguage,
    RepositoryTopic,
)
from services.profiling.manifests import is_manifest, parse_manifest

from .client import GitHubClient, GitHubRepo
from .errors import GitHubNotFound


def upsert_repository(gh: GitHubRepo, now: Any) -> Repository:
    # A different repo that used to have this name (deleted and recreated, or renamed away) is
    # stale; drop it so the unique full_name can move to the current repo.
    Repository.objects.filter(full_name=gh.full_name).exclude(github_id=gh.github_id).delete()
    repo, _ = Repository.objects.update_or_create(
        github_id=gh.github_id,
        defaults={
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
            "synced_at": now,
        },
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


def read_manifests(client: GitHubClient, full_name: str) -> dict[tuple[str, str], str]:
    """``{(ecosystem, name): manifest path}`` from the repository's root manifests."""
    found: dict[tuple[str, str], str] = {}
    for entry in client.list_root_contents(full_name):
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
