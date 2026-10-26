"""Recommendation data model (Phase 5, group 1)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse
from django.utils import timezone

from developers.models import DeveloperProfile
from e2e.builders import make_candidate_repo
from recommendations.models import (
    ImmutableConfig,
    Recommendation,
    RecommendationReason,
    ScoringConfig,
)
from services.ranking.config import V1_PARAMS, V1_WEIGHTS, V2_PARAMS, V2_WEIGHTS

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def make_recommendation(profile, repo, config=None, rank=1) -> Recommendation:
    return Recommendation.objects.create(
        developer=profile,
        repository=repo,
        scoring_config=config or ScoringConfig.objects.get(is_active=True),
        score=0.5,
        signal_scores={"skill": 0.5},
        rank=rank,
        match_label="good",
        size="unknown",
        generated_at=timezone.now(),
    )


def test_seeds_v1_stored_and_v2_active() -> None:
    v1 = ScoringConfig.objects.get(version="v1-deterministic")
    assert not v1.is_active
    assert (v1.weights, v1.params) == (V1_WEIGHTS, V1_PARAMS)
    v2 = ScoringConfig.objects.get(version="v2-deterministic")
    assert v2.is_active
    assert (v2.weights, v2.params) == (V2_WEIGHTS, V2_PARAMS)
    assert "experimental" in v2.description.lower()
    v2.full_clean()  # no ValidationError


def test_only_one_active_config() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ScoringConfig.objects.create(
            version="v3", weights=V2_WEIGHTS, params=V2_PARAMS, is_active=True
        )


def test_invalid_weights_rejected_by_clean() -> None:
    config = ScoringConfig(version="bad", weights={**V2_WEIGHTS, "skill": 0.30}, params=V2_PARAMS)
    with pytest.raises(ValidationError, match="sum to 1"):
        config.full_clean()


def unused_config() -> ScoringConfig:
    return ScoringConfig.objects.create(version="v3-unused", weights=V2_WEIGHTS, params=V2_PARAMS)


@pytest.mark.parametrize("field", ["version", "weights", "params"])
def test_stored_config_numbers_cannot_change(field: str) -> None:
    config = unused_config()
    changed = {
        "version": "v3-renamed",
        "weights": {**V2_WEIGHTS, "skill": 0.30, "language": 0.20},
        "params": {**V2_PARAMS, "min_score": 0.05},
    }[field]
    setattr(config, field, changed)
    with pytest.raises(ImmutableConfig, match=field):
        config.save()
    stored = ScoringConfig.objects.get(pk=config.pk)
    assert (stored.version, stored.weights, stored.params) == ("v3-unused", V2_WEIGHTS, V2_PARAMS)


def test_stored_config_activation_and_description_stay_writable() -> None:
    config = unused_config()
    ScoringConfig.objects.filter(is_active=True).update(is_active=False)
    config.is_active = True
    config.description = "Promoted"
    config.save()
    config.weights = {**V2_WEIGHTS, "skill": 0.30, "language": 0.20}  # not saved below
    config.save(update_fields=["is_active", "description"])
    stored = ScoringConfig.objects.get(pk=config.pk)
    assert (stored.is_active, stored.description, stored.weights) == (True, "Promoted", V2_WEIGHTS)


def test_description_edit_with_json_equal_values_is_allowed() -> None:
    # A tuple is stored as a list: the same numbers, so no ImmutableConfig.
    config = ScoringConfig.objects.create(
        version="v3-tuple", weights=V2_WEIGHTS, params={**V2_PARAMS, "note": (0.3, 0.6)}
    )
    config.description = "Edited"
    config.save()
    assert ScoringConfig.objects.get(pk=config.pk).description == "Edited"


def test_admin_shows_stored_numbers_read_only(admin_client) -> None:
    config = unused_config()
    response = admin_client.get(
        reverse("admin:recommendations_scoringconfig_change", args=[config.pk])
    )
    assert response.status_code == 200
    form = response.context["adminform"].form
    assert not {"version", "weights", "params"} & set(form.fields)
    assert "description" in form.fields


def test_config_in_use_cannot_be_deleted(profile) -> None:
    make_recommendation(profile, make_candidate_repo(1))
    with pytest.raises(ProtectedError):
        ScoringConfig.objects.get(version="v2-deterministic").delete()


def test_recommendations_cascade_with_profile(profile) -> None:
    rec = make_recommendation(profile, make_candidate_repo(1))
    RecommendationReason.objects.create(
        recommendation=rec, type="skill", text="t", weight=0.1, position=0
    )
    profile.delete()
    assert not Recommendation.objects.exists()
    assert not RecommendationReason.objects.exists()


def test_unique_developer_repository(profile) -> None:
    repo = make_candidate_repo(1)
    make_recommendation(profile, repo)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_recommendation(profile, repo, rank=2)
