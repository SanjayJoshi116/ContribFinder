"""Stored GitHub data for profile analysis and API tests."""

from datetime import timedelta

import pytest
from django.utils import timezone

from github.models import GitHubProfile
from repositories.models import (
    Repository,
    RepositoryDependency,
    RepositoryLanguage,
    RepositoryTopic,
    UserRepository,
)

README = "## Tech Stack\nPython, Django, Docker\n\nI build developer tools."


def add_repo(user, n: int, *, relation: str = "owner", languages=None, topics=(), deps=(), **kw):
    repo = Repository.objects.create(
        github_id=1000 + n,
        owner_login="octocat" if relation == "owner" else "upstream",
        name=f"r{n}",
        full_name=f"{'octocat' if relation == 'owner' else 'upstream'}/r{n}",
        html_url=f"https://github.com/x/r{n}",
        pushed_at=timezone.now() - timedelta(days=n),
        synced_at=timezone.now(),
        **kw,
    )
    for lang, size in (languages or {"Python": 1000}).items():
        RepositoryLanguage.objects.create(repository=repo, language=lang, bytes=size)
    for topic in topics:
        RepositoryTopic.objects.create(repository=repo, topic=topic)
    for eco, name in deps:
        RepositoryDependency.objects.create(
            repository=repo, ecosystem=eco, name=name, manifest_path="pyproject.toml"
        )
    extra = {"merged_pr_count": 4, "push_count": 1} if relation == "contributor" else {}
    UserRepository.objects.create(user=user, repository=repo, relation=relation, **extra)
    return repo


@pytest.fixture
def synced(user):
    GitHubProfile.objects.create(
        user=user,
        github_id=1,
        login="octocat",
        has_profile_readme=True,
        profile_readme=README,
        github_created_at=timezone.now() - timedelta(days=5 * 365),
        synced_at=timezone.now(),
    )
    add_repo(user, 1, topics=("developer-tools", "kubernetes"), deps=[("pypi", "django")])
    add_repo(user, 2, topics=("cli",))
    add_repo(user, 3, relation="contributor", languages={"Go": 500}, topics=("devops",))
    return user
