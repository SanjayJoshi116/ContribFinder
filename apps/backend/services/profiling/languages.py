"""Language breakdown across the user's own (non-fork) repositories."""

from __future__ import annotations

from collections import Counter
from typing import TypedDict

from .inputs import ProfileInput


class LanguageShare(TypedDict):
    name: str
    bytes: int
    share: float
    repo_count: int


def aggregate_languages(profile: ProfileInput) -> list[LanguageShare]:
    totals: Counter[str] = Counter()
    repos: Counter[str] = Counter()
    for repo in profile.own_work:
        for language, count in repo.languages.items():
            if count > 0:
                totals[language] += count
                repos[language] += 1
    grand_total = sum(totals.values())
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return [
        LanguageShare(
            name=name,
            bytes=count,
            share=round(count / grand_total, 2),
            repo_count=repos[name],
        )
        for name, count in ordered
    ]
