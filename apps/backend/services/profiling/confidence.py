"""Evidence → confidence (spec: skill-detection, "Confidence with diminishing returns").

Noisy-OR over evidence items: the k-th item (0-based) from a source counts with weight
``w_source · decay**k``, so repeated evidence from one source adds progressively less, while
independent sources compound. One README mention alone gives exactly the README weight. The
result is capped below 1, because evidence of use is never proof of expertise.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping

from .inputs import Evidence


def compute_confidence(
    evidence: Iterable[Evidence],
    weights: Mapping[str, float],
    *,
    decay: float,
    cap: float,
) -> float:
    remaining_doubt = 1.0
    for source, count in Counter(e.source for e in evidence).items():
        weight = weights.get(source, 0.0)
        for k in range(count):
            remaining_doubt *= 1 - weight * decay**k
    return round(min(1 - remaining_doubt, cap), 4)
