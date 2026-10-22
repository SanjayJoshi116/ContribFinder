"""Fixtures shared by the discovery and repository-analysis tests. Imported by the modules
that use them, not put in ``conftest.py``: a global ``client`` fixture would replace
pytest-django's test client in every other module."""

from collections.abc import Iterator

import pytest
from django.utils import timezone

from developers.models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    Interest,
    Skill,
    SkillEvidence,
)
from github.models import GitHubProfile
from services.github.client import PUBLIC_SCOPE, GitHubClient

from .test_github_client import TOKEN


def make_developer(
    user,
    login: str = "octocat",
    *,
    skills=(("python", "language"),),
    interests=("developer-tooling",),
) -> DeveloperProfile:
    GitHubProfile.objects.create(
        user=user, github_id=user.pk, login=login, synced_at=timezone.now()
    )
    profile = DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())
    for slug, category in skills:
        skill, _ = Skill.objects.get_or_create(
            slug=slug, defaults={"name": slug, "category": category}
        )
        ds = DeveloperSkill.objects.create(profile=profile, skill=skill, confidence=0.8)
        SkillEvidence.objects.create(developer_skill=ds, source="language")
    for slug in interests:
        interest, _ = Interest.objects.get_or_create(slug=slug, defaults={"name": slug})
        DeveloperInterest.objects.create(profile=profile, interest=interest, strength=0.6)
    return profile


@pytest.fixture(autouse=True)
def single_band(settings) -> None:
    """One open-ended band: the pre-band plan shape, so provenance reads ``language:Python``.
    Banded runs override this explicitly. Autouse in every module that imports it."""
    settings.DISCOVERY_STAR_BANDS = [[20, None]]
    settings.DISCOVERY_MAX_QUERIES = 10


@pytest.fixture
def developer(user) -> DeveloperProfile:
    return make_developer(user)


@pytest.fixture(name="client")
def public_client() -> Iterator[GitHubClient]:
    """A GitHub client in the shared public cache scope (repository analysis)."""
    with GitHubClient(TOKEN, cache_scope=PUBLIC_SCOPE) as c:
        yield c
