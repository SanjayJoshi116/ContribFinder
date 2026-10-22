"""Profile summary from fixed templates filled only with computed signals (never free text)."""

from __future__ import annotations

from collections.abc import Sequence

from services.text import join_names

SPARSE = "Not enough public activity was found to describe your technical profile yet."


def _in_sentence(name: str) -> str:
    """Lowercase a leading ordinary word ("Developer tooling" → "developer tooling") but keep
    acronyms and product-style names ("AI", "DevOps")."""
    first, _, rest = name.partition(" ")
    if first[:1].isupper() and first[1:].islower():
        first = first.lower()
    return f"{first} {rest}".strip()


def build_summary(
    languages: Sequence[str], frameworks: Sequence[str], interests: Sequence[str]
) -> str:
    """``languages``: top languages by skill confidence; ``frameworks``: top framework/library
    skill names by confidence; ``interests``: top interest names by strength. Each is truncated
    here."""
    sentences = []
    if languages:
        sentences.append(f"Works mostly in {join_names(list(languages[:2]))}.")
    if frameworks:
        sentences.append(f"Frequently uses {join_names(list(frameworks[:3]))}.")
    if interests:
        names = [_in_sentence(i) for i in interests[:2]]
        sentences.append(f"Interested in {join_names(names)}.")
    if not languages and not frameworks:
        return SPARSE if not interests else f"{SPARSE} {sentences[-1]}"
    return " ".join(sentences)
