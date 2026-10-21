"""One lock order for a developer's recommendations and feedback state (spec:
recommendation-feedback; recommendation-consistency design D2).

Everything that writes a developer's recommendations, saves or dismissals locks the
developer profile row first, inside its transaction, so these writes run one at a time per
developer and never wait on each other in a cycle. The order is:

    job row (``job_write``, generation only)
      → developer profile row (``lock_developer``)
        → dismissals and saves (read or written)
          → Recommendation rows
            → Issue rows, ordered by pk
              → children (reasons, recommended issues)

Two writers start further down the order and hold nothing above it: recording an event
locks only that recommendation's row, and an issue refresh locks all of the repository's
issues, ordered by pk, before deleting or updating any, so an issue's lock always comes
before its recommended-issue rows.
"""

from __future__ import annotations

from developers.models import DeveloperProfile


def lock_developer(user_id: int) -> DeveloperProfile | None:
    """Lock and return the user's developer profile, or None when there is none. Call inside
    a transaction, before touching any other row of the order above."""
    return DeveloperProfile.objects.select_for_update().filter(user_id=user_id).first()
