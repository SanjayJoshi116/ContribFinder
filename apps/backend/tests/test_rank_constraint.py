"""Stored ranks start at 1 (change rank-constraint, Bug_Backlog T-12)."""

from typing import Any, cast

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Model
from django.utils import timezone

from accounts.models import User
from developers.models import DeveloperProfile
from e2e.builders import make_candidate_repo, make_issue
from feedback.models import RecommendationFeedback
from issues.models import RecommendedIssue
from recommendations.models import Recommendation, ScoringConfig
from services.ranking.config import V2_PARAMS, V2_WEIGHTS

from .factories import UserFactory
from .test_models_phase5 import make_recommendation

pytestmark = pytest.mark.django_db


def profile_for(user: User) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def event(user: User, rank: int | None) -> RecommendationFeedback:
    return RecommendationFeedback.objects.create(
        user=user, repository_full_name="o/r", action="viewed", rank=rank
    )


def issue_for(rec: Recommendation, number: int, rank: int) -> RecommendedIssue:
    return RecommendedIssue.objects.create(
        recommendation=rec, issue=make_issue(rec.repository, number), rank=rank, score=0.5
    )


def refused(create: Any) -> bool:
    try:
        with transaction.atomic():
            create()
    except IntegrityError:
        return True
    return False


# --- The database refuses rank 0 -----------------------------------------------------------


def test_recommendation_rank_0_refused(user) -> None:
    profile = profile_for(user)
    assert refused(lambda: make_recommendation(profile, make_candidate_repo(1), rank=0))
    assert not Recommendation.objects.exists()


def test_recommended_issue_rank_0_refused(user) -> None:
    rec = make_recommendation(profile_for(user), make_candidate_repo(1))
    assert refused(lambda: issue_for(rec, 1, rank=0))
    assert not RecommendedIssue.objects.exists()


def test_feedback_rank_0_refused_null_stored(user) -> None:
    assert refused(lambda: event(user, rank=0))
    assert event(user, rank=None).rank is None
    assert event(user, rank=1).rank == 1


# --- The upgrade repairs, never deletes ----------------------------------------------------

BEFORE = [
    ("recommendations", "0004_issue_snapshots_and_reason_types"),
    ("issues", "0001_initial"),
    ("feedback", "0004_dismiss_reasons"),
]


@pytest.mark.django_db(transaction=True)
def test_upgrade_repairs_rank_0_and_adds_the_constraints(user) -> None:
    """The real upgrade path: back before the three migrations (no constraints, same columns),
    store rank 0 rows, migrate forward. Groups with a rank 0 shift up in order, other groups and
    rows stay, event rank 0 becomes null, nothing is deleted."""
    executor = MigrationExecutor(connection)
    latest = [node for app, _ in BEFORE for node in executor.loader.graph.leaf_nodes(app)]
    executor.migrate(BEFORE)

    config = ScoringConfig.objects.create(
        version="test-rank-repair", weights=V2_WEIGHTS, params=V2_PARAMS, is_active=False
    )
    profile = profile_for(user)
    other = profile_for(cast(User, UserFactory()))
    untouched = make_recommendation(other, make_candidate_repo(10), config=config, rank=1)
    recs = [
        make_recommendation(profile, make_candidate_repo(i), config=config, rank=i)
        for i in (0, 1, 2)
    ]
    issues = [issue_for(recs[1], n, rank=n) for n in (0, 1, 2)]
    clean_issue = issue_for(recs[2], 9, rank=1)
    zero, three = event(user, rank=0), event(user, rank=3)

    executor.loader.build_graph()
    executor.migrate(latest)

    def rank(model: type[Model], pk: int) -> int | None:
        return cast(int | None, model._default_manager.values_list("rank", flat=True).get(pk=pk))

    assert [rank(Recommendation, r.pk) for r in recs] == [1, 2, 3]
    assert rank(Recommendation, untouched.pk) == 1
    assert [rank(RecommendedIssue, i.pk) for i in issues] == [1, 2, 3]
    assert rank(RecommendedIssue, clean_issue.pk) == 1
    assert (rank(RecommendationFeedback, zero.pk), rank(RecommendationFeedback, three.pk)) == (
        None,
        3,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conname LIKE %s", ["%rank_positive"]
        )
        stored = {row[0] for row in cursor.fetchall()}
    assert {
        "recommendation_rank_positive",
        "recommended_issue_rank_positive",
        "feedback_rank_positive",
    } <= stored
