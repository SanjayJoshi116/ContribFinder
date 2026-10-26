"""How users acted on recommendations, per scoring configuration (spec:
recommendation-evaluation "Feedback report"; changes feedback-report,
feedback-report-labels and dismiss-reasons).

``load`` is the one query; ``build`` is pure. There is no "shown" event, so shares are of
decisive actions (positive or dismissed), not of recommendations shown. Aggregates only: user
ids are used to count distinct users and never leave ``build``.
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


def bucket_label(bucket: tuple[int, int | None]) -> str:
    first, last = bucket
    return f"{first}+" if last is None else f"{first}-{last}"


def _bucket(rank: int) -> tuple[int, int | None]:
    """The bucket of a rank of at least 1."""
    return next(b for b in BUCKETS if b[0] <= rank and (b[1] is None or rank <= b[1]))


def _share(positive: int, decisive: int, minimum: int) -> float | None:
    return positive / decisive if decisive >= minimum and decisive else None


def _total(counts: Counter[str] | dict[str, int], actions: Iterable[str]) -> int:
    return sum(counts.get(a, 0) for a in actions)


# Per group key: the count of each action and the distinct users.
Groups = dict[tuple[str, Any], tuple[Counter[str], set[int]]]


def _add(groups: Groups, key: tuple[str, Any], event: Event) -> None:
    tally, users = groups.setdefault(key, (Counter(), set()))
    tally[event.action] += 1
    users.add(event.user_id)


def _tally(group: Counter[str], minimum: int) -> tuple[dict[str, int], float | None]:
    """A group's count of every action and its positive share."""
    share = _share(_total(group, POSITIVE), _total(group, DECISIVE), minimum)
    return {action: group[action] for action in ACTIONS}, share


def _rows[K](
    groups: Groups, version: str, keys: Iterable[K], minimum: int
) -> list[tuple[K, dict[str, int], int, float | None]]:
    """``(key, counts, users, share)`` for each of a version's keys that has events."""
    rows = []
    for key in keys:
        if (group := groups.get((version, key))) is not None:
            tally, users = group
            counts, share = _tally(tally, minimum)
            rows.append((key, counts, len(users), share))
    return rows


def _reasons(tally: Counter[str]) -> dict[str, int]:
    """Dismissals per reason, most frequent first, dismissals without one last."""
    found = sorted(
        ((reason, tally[reason]) for reason in REASONS if tally[reason]),
        key=lambda item: -item[1],
    )
    if tally[NO_REASON]:
        found.append((NO_REASON, tally[NO_REASON]))
    return dict(found)


def calibration(rows: Iterable[LabelRow]) -> Calibration:
    """``ordered`` when no label's share is below a lower label's (ties are ordered)."""
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
    counts: dict[str, int]  # every action, 0 when absent
    users: int
    share: float | None  # None below the minimum

    @property
    def decisive(self) -> int:
        return _total(self.counts, DECISIVE)

    @property
    def positive(self) -> int:
        return _total(self.counts, POSITIVE)


@dataclass(frozen=True)
class LabelRow:
    label: str
    counts: dict[str, int]
    users: int
    share: float | None  # not adjusted for rank


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
    return {name_key: name, "counts": row.counts, "users": row.users, "share": _rounded(row.share)}


def load(since: datetime | None, versions: Sequence[str] = ()) -> Iterator[Event]:
    """Every feedback event in the window (all time without ``since``), optionally only for
    some configuration versions. One query, streamed in chunks and unordered: ``build`` only
    counts."""
    rows = RecommendationFeedback.objects.order_by()
    if since is not None:
        rows = rows.filter(created_at__gte=since)
    if versions:
        rows = rows.filter(config_version__in=versions)
    fields = ("user_id", "action", "config_version", "rank", "match_label", "dismiss_reason")
    return (Event(*row) for row in rows.values_list(*fields).iterator(chunk_size=2000))


def build(
    events: Iterable[Event], *, minimum: int = DEFAULT_MINIMUM, since_days: int | None = None
) -> FeedbackReport:
    if minimum < 1:
        raise ValueError("minimum must be at least 1")
    buckets: Groups = {}  # (version, bucket)
    labels: Groups = {}  # (version, match label)
    reasons: dict[str, Counter[str]] = {}
    unattributed: Counter[str] = Counter()
    unattributed_reasons: Counter[str] = Counter()
    for event in events:
        reason = event.dismiss_reason or NO_REASON
        dismissed = event.action == FeedbackAction.DISMISSED
        # A rank below 1 is no rank: generation ranks from 1.
        if not event.config_version or event.rank is None or event.rank < 1:
            unattributed[event.action] += 1
            if dismissed:
                unattributed_reasons[reason] += 1
            continue
        _add(buckets, (event.config_version, _bucket(event.rank)), event)
        if event.match_label:
            _add(labels, (event.config_version, event.match_label), event)
        if dismissed:
            reasons.setdefault(event.config_version, Counter())[reason] += 1

    # The common bucket mix for the position adjustment: decisive actions over every config.
    weight: Counter[Any] = Counter()
    for key, (tally, _) in buckets.items():
        weight[key[1]] += _total(tally, DECISIVE)

    configs = []
    for version in sorted({key[0] for key in buckets}):
        rows = [BucketRow(*row) for row in _rows(buckets, version, BUCKETS, minimum)]
        label_rows = [LabelRow(*row) for row in _rows(labels, version, LABELS, minimum)]
        shared = [(row.bucket, row.share) for row in rows if row.share is not None]
        total = sum(weight[bucket] for bucket, _ in shared)
        adjusted = (
            sum(weight[bucket] * share for bucket, share in shared) / total
            if shared and total
            else None
        )
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
            )
        )
    return FeedbackReport(
        minimum,
        tuple(configs),
        {action: unattributed[action] for action in ACTIONS if unattributed[action]},
        since_days,
        _reasons(unattributed_reasons),
    )
