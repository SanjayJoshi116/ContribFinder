"""How users acted on recommendations, per scoring configuration (spec:
recommendation-evaluation "Feedback report"; changes feedback-report,
feedback-report-labels, dismiss-reasons and services-evaluation-review-fixes).

``load`` is the one query; ``build`` is pure. There is no "shown" event, so shares are of
decisive outcomes (positive or dismissed), not of recommendations shown. Shares count outcomes,
not events: each user, repository and configuration version has at most one, its latest
decisive event that was not undone (design D3). Action counts stay raw event counts.
Aggregates only: user ids and repository names are used to group events and never leave
``build``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NamedTuple

from feedback.models import DismissReason, FeedbackAction, RecommendationFeedback
from recommendations.models import MatchLabel

from .metrics import PLACES

# (first rank, last rank or None for open-ended), best first.
BUCKETS: tuple[tuple[int, int | None], ...] = ((1, 5), (6, 10), (11, 20), (21, None))
POSITIVE = frozenset(
    {FeedbackAction.SAVED, FeedbackAction.OPENED_REPOSITORY, FeedbackAction.OPENED_ISSUE}
)
DECISIVE = POSITIVE | {FeedbackAction.DISMISSED}
# What an undo event takes back: the latest event of this action before it.
UNDOES = {
    str(FeedbackAction.UNSAVED): str(FeedbackAction.SAVED),
    str(FeedbackAction.UNDISMISSED): str(FeedbackAction.DISMISSED),
}
ACTIONS = tuple(str(action) for action in FeedbackAction)
DEFAULT_MINIMUM = 10
# Best first; the calibration verdict expects shares in this order.
LABELS = tuple(str(label) for label in MatchLabel)
ORDERED, NOT_ORDERED, NOT_ENOUGH = "ordered", "not ordered", "not enough data"
REASONS = tuple(str(reason) for reason in DismissReason)
NO_REASON = "none"  # a dismissal without a reason


class Event(NamedTuple):
    user_id: int
    action: str
    config_version: str  # "" when there was no recommendation
    rank: int | None
    match_label: str = ""  # "" when there was no recommendation
    dismiss_reason: str = ""  # dismissed only; "" when none was given
    repository: str = ""  # the repository's full name; groups events into outcomes


def bucket_label(bucket: tuple[int, int | None]) -> str:
    first, last = bucket
    return f"{first}+" if last is None else f"{first}-{last}"


def _bucket(rank: int) -> tuple[int, int | None]:
    """The bucket of a rank of at least 1."""
    return next(b for b in BUCKETS if b[0] <= rank and (b[1] is None or rank <= b[1]))


def _share(positive: int, decisive: int, minimum: int) -> float | None:
    return positive / decisive if decisive >= minimum and decisive else None


# Per group key: the count of each action (every event) and the distinct users.
Groups = dict[tuple[str, Any], tuple[Counter[str], set[int]]]
# Per group key: [positive, decisive] outcomes.
Outcomes = dict[tuple[str, Any], list[int]]


def _add(groups: Groups, key: tuple[str, Any], event: Event) -> None:
    tally, users = groups.setdefault(key, (Counter(), set()))
    tally[event.action] += 1
    users.add(event.user_id)


def _outcome(outcomes: Outcomes, key: tuple[str, Any], action: str) -> None:
    tally = outcomes.setdefault(key, [0, 0])
    tally[0] += action in POSITIVE
    tally[1] += 1


def _rows[K](
    groups: Groups, outcomes: Outcomes, version: str, keys: Iterable[K], minimum: int
) -> list[tuple[K, dict[str, int], int, float | None, int, int]]:
    """``(key, counts, users, share, positive, decisive)`` for each of a version's keys that has
    events; the share and the two outcome counts come from outcomes."""
    rows = []
    for key in keys:
        if (group := groups.get((version, key))) is not None:
            tally, users = group
            positive, decisive = outcomes.get((version, key), (0, 0))
            counts = {action: tally[action] for action in ACTIONS}
            share = _share(positive, decisive, minimum)
            rows.append((key, counts, len(users), share, positive, decisive))
    return rows


def _reasons(tally: Counter[str]) -> dict[str, int]:
    """Dismissals per reason, most frequent first: the current reasons, then stored values that
    are no longer offered, then dismissals without a reason."""
    known = sorted(
        ((reason, tally[reason]) for reason in REASONS if tally[reason]),
        key=lambda item: -item[1],
    )
    other = sorted(
        ((reason, n) for reason, n in tally.items() if n and reason not in {*REASONS, NO_REASON}),
        key=lambda item: (-item[1], item[0]),
    )
    found = [*known, *other]
    if tally[NO_REASON]:
        found.append((NO_REASON, tally[NO_REASON]))
    return dict(found)


def calibration(rows: Iterable[LabelRow]) -> Calibration:
    """``ordered`` when no label's share is below a lower label's (ties are ordered). Only the
    current labels take part."""
    shares = {row.label: row.share for row in rows if row.share is not None}
    present = [label for label in LABELS if label in shares]
    if len(present) < 2:
        return Calibration(NOT_ENOUGH)
    for i, higher in enumerate(present):
        for lower in present[i + 1 :]:
            if shares[higher] < shares[lower]:
                return Calibration(NOT_ORDERED, higher, lower)
    return Calibration(ORDERED)


@dataclass(frozen=True)
class BucketRow:
    bucket: tuple[int, int | None]
    counts: dict[str, int]  # every action (raw events), 0 when absent
    users: int
    share: float | None  # None below the minimum
    positive: int  # outcomes
    decisive: int


@dataclass(frozen=True)
class LabelRow:
    label: str
    counts: dict[str, int]
    users: int
    share: float | None  # not adjusted for rank
    positive: int
    decisive: int


@dataclass(frozen=True)
class Calibration:
    verdict: str  # ORDERED, NOT_ORDERED or NOT_ENOUGH
    higher: str | None = None  # NOT_ORDERED: the higher label whose share is lower
    lower: str | None = None


@dataclass(frozen=True)
class ConfigRows:
    version: str
    buckets: tuple[BucketRow, ...]  # only buckets with events
    raw_share: float | None
    adjusted_share: float | None
    labels: tuple[LabelRow, ...] = ()  # only labels with events
    calibration: Calibration = Calibration(NOT_ENOUGH)
    # Dismissals per reason (NO_REASON without one); never part of a share.
    dismiss_reasons: dict[str, int] = field(default_factory=dict)
    # The part of the report's bucket weight carried by the buckets of the adjusted share.
    coverage: float | None = None


@dataclass(frozen=True)
class FeedbackReport:
    minimum: int
    configs: tuple[ConfigRows, ...]
    unattributed: dict[str, int] = field(default_factory=dict)
    since_days: int | None = None
    # Reasons of the unattributed dismissals (``NO_REASON`` without one); in no share.
    unattributed_dismiss_reasons: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "since_days": self.since_days,
            "minimum": self.minimum,
            "configs": [
                {
                    "version": c.version,
                    "raw_share": _rounded(c.raw_share),
                    "adjusted_share": _rounded(c.adjusted_share),
                    "coverage": _rounded(c.coverage),
                    "buckets": [
                        _row_dict("ranks", bucket_label(row.bucket), row) for row in c.buckets
                    ],
                    "labels": [_row_dict("label", row.label, row) for row in c.labels],
                    "calibration": {
                        "verdict": c.calibration.verdict,
                        "higher": c.calibration.higher,
                        "lower": c.calibration.lower,
                    },
                    "dismiss_reasons": c.dismiss_reasons,
                }
                for c in self.configs
            ],
            "unattributed": self.unattributed,
            "unattributed_dismiss_reasons": self.unattributed_dismiss_reasons,
        }


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, PLACES)


def _row_dict(name_key: str, name: str, row: BucketRow | LabelRow) -> dict[str, Any]:
    return {
        name_key: name,
        "counts": row.counts,
        "users": row.users,
        "positive": row.positive,
        "decisive": row.decisive,
        "share": _rounded(row.share),
    }


def load(since: datetime | None) -> Iterator[Event]:
    """Every feedback event in the window (all time without ``since``), oldest first (``build``
    reads undo events in order). One query, streamed in chunks. Never filtered by version: an
    undo carries no version or a later one, so ``build(versions=)`` narrows the report after
    settling outcomes."""
    rows = RecommendationFeedback.objects.order_by("created_at", "id")
    if since is not None:
        rows = rows.filter(created_at__gte=since)
    fields = (
        "user_id",
        "action",
        "config_version",
        "rank",
        "match_label",
        "dismiss_reason",
        "repository_full_name",
    )
    return (Event(*row) for row in rows.values_list(*fields).iterator(chunk_size=2000))


class Decision(NamedTuple):
    """What an outcome needs from a decisive event."""

    action: str
    version: str
    bucket: tuple[int, int | None]
    match_label: str


# Per (user, repository): the decisive events not undone, oldest first. Not keyed by version:
# an undo carries no version (restore) or a later one (unsave after a regeneration).
Stacks = dict[tuple[int, str], list[Decision]]


def _rank(event: Event) -> int | None:
    """The event's rank when it is attributed (a version and a rank of at least 1)."""
    if not event.config_version or event.rank is None or event.rank < 1:
        return None  # a rank below 1 is no rank: generation ranks from 1
    return event.rank


def _settle(stacks: Stacks, event: Event, rank: int | None) -> None:
    """Keep each (user, repository)'s decisive events that were not undone, in order. An undo
    event takes back the latest event it undoes, whatever its own version and rank."""
    key = (event.user_id, event.repository)
    if event.action in UNDOES:
        stack = stacks.get(key, [])
        undone = UNDOES[event.action]
        for index in range(len(stack) - 1, -1, -1):
            if stack[index].action == undone:
                del stack[index]
                break
    elif rank is not None and event.action in DECISIVE:
        decision = Decision(event.action, event.config_version, _bucket(rank), event.match_label)
        stacks.setdefault(key, []).append(decision)


def build(
    events: Iterable[Event],
    *,
    minimum: int = DEFAULT_MINIMUM,
    since_days: int | None = None,
    versions: Sequence[str] = (),
) -> FeedbackReport:
    """``events`` in the order they happened. With ``versions``, only those configuration
    versions are reported (no unattributed events), but every event still settles outcomes, so
    an undo of another version (or none) takes back a decision of a reported one."""
    wanted = frozenset(versions)
    if minimum < 1:
        raise ValueError("minimum must be at least 1")
    buckets: Groups = {}  # (version, bucket)
    labels: Groups = {}  # (version, match label)
    stacks: Stacks = {}
    reasons: dict[str, Counter[str]] = {}
    unattributed: Counter[str] = Counter()
    unattributed_reasons: Counter[str] = Counter()
    for event in events:
        reason = event.dismiss_reason or NO_REASON
        dismissed = event.action == FeedbackAction.DISMISSED
        rank = _rank(event)
        _settle(stacks, event, rank)
        if wanted and event.config_version not in wanted:
            continue
        if rank is None:
            unattributed[event.action] += 1
            if dismissed:
                unattributed_reasons[reason] += 1
            continue
        _add(buckets, (event.config_version, _bucket(rank)), event)
        if event.match_label:
            _add(labels, (event.config_version, event.match_label), event)
        if dismissed:
            reasons.setdefault(event.config_version, Counter())[reason] += 1

    bucket_outcomes: Outcomes = {}
    label_outcomes: Outcomes = {}
    for stack in stacks.values():
        latest = {decision.version: decision for decision in stack}  # per version, its last
        for version, last in latest.items():
            if wanted and version not in wanted:
                continue
            _outcome(bucket_outcomes, (version, last.bucket), last.action)
            if last.match_label:
                _outcome(label_outcomes, (version, last.match_label), last.action)

    # The common bucket mix for the position adjustment: decisive outcomes over every config.
    weight: Counter[Any] = Counter()
    for (_, bucket), (_, decisive) in bucket_outcomes.items():
        weight[bucket] += decisive
    everything = sum(weight.values())

    configs = []
    for version in sorted({key[0] for key in buckets}):
        rows = [
            BucketRow(*row) for row in _rows(buckets, bucket_outcomes, version, BUCKETS, minimum)
        ]
        stored = sorted({key[1] for key in labels if key[0] == version} - set(LABELS))
        label_keys = [*LABELS, *stored]
        label_rows = [
            LabelRow(*row) for row in _rows(labels, label_outcomes, version, label_keys, minimum)
        ]
        shared = [(row.bucket, row.share) for row in rows if row.share is not None]
        total = sum(weight[bucket] for bucket, _ in shared)
        adjusted = coverage = None
        if shared and total:
            adjusted = sum(weight[bucket] * share for bucket, share in shared) / total
            coverage = total / everything
        configs.append(
            ConfigRows(
                version,
                tuple(rows),
                _share(
                    sum(row.positive for row in rows), sum(row.decisive for row in rows), minimum
                ),
                adjusted,
                tuple(label_rows),
                calibration(label_rows),
                _reasons(reasons.get(version, Counter())),
                coverage,
            )
        )
    return FeedbackReport(
        minimum,
        tuple(configs),
        {action: unattributed[action] for action in ACTIONS if unattributed[action]},
        since_days,
        _reasons(unattributed_reasons),
    )
