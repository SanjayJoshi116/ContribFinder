"""The candidate pool order (spec: "Candidate pool maintenance"): previously interacted
first, then best search rank, then most recently found, then repository name. The pool cap
keeps candidates in this order, discovery analyzes them in it, and the candidate list shows
them in it, so the three cannot drift."""

from __future__ import annotations

from typing import Any

from django.db.models import Exists, F, OuterRef, QuerySet, Subquery

from repositories.models import CandidateDiscovery, DiscoverySource, RepositoryCandidate


def pool_order(
    queryset: QuerySet[RepositoryCandidate], *leading: Any
) -> QuerySet[RepositoryCandidate]:
    """``queryset`` annotated with ``interacted`` and ``best_rank`` and ordered by ``leading``
    then the pool order. Subqueries, not an aggregate: no GROUP BY, so it combines with
    ``select_related`` and other annotations."""
    interacted = CandidateDiscovery.objects.filter(
        candidate=OuterRef("pk"), source=DiscoverySource.PREVIOUSLY_INTERACTED
    )
    best_rank = (
        CandidateDiscovery.objects.filter(candidate=OuterRef("pk"), search_rank__isnull=False)
        .order_by("search_rank")
        .values("search_rank")[:1]
    )
    return queryset.annotate(interacted=Exists(interacted), best_rank=Subquery(best_rank)).order_by(
        *leading,
        F("interacted").desc(),
        F("best_rank").asc(nulls_last=True),
        F("last_seen_at").desc(),
        "repository__full_name",
    )
