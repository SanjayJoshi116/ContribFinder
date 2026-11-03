"""Fixtures shared by the discovery and repository-analysis tests. Imported by the modules
that use them, not put in ``conftest.py``: a global ``client`` fixture would replace
pytest-django's test client in every other module."""

from collections.abc import Callable, Iterator

import pytest
from django.contrib.admin.sites import site
from django.db import connection
from django.db.models import Model
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
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
from recommendations.models import ScoringConfig
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


def active_configs() -> list[str]:
    return list(ScoringConfig.objects.filter(is_active=True).values_list("version", flat=True))


def assert_view_only(model: type[Model], user, obj: Model | None = None) -> None:
    """Staff (``user``) may view ``model`` in the admin and never add, change or delete it,
    nor delete through its inlines (``core.admin.ViewOnlyAdmin``)."""
    request = RequestFactory().get("/admin/")
    request.user = user
    admin = site._registry[model]
    assert not admin.has_add_permission(request)
    assert not admin.has_change_permission(request, obj)
    assert not admin.has_delete_permission(request, obj)
    assert admin.has_view_permission(request, obj)
    for inline in admin.inlines:
        assert inline.can_delete is False


def changelist_queries(client: Client, url: str) -> int:
    """Queries one admin changelist page runs (``client`` signed in as staff)."""
    with CaptureQueriesContext(connection) as captured:
        assert client.get(url).status_code == 200
    return len(captured)


def assert_changelist_flat(client: Client, url: str, make: Callable[[int], object]) -> None:
    """The changelist at ``url`` runs as many queries for four rows as for one; ``make(n)``
    builds the ``n``-th row."""
    make(1)
    one = changelist_queries(client, url)
    for n in range(2, 5):
        make(n)
    assert changelist_queries(client, url) == one
