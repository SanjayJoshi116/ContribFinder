"""Profile analysis (design D6): stored GitHub data → DeveloperProfile, skills, interests.

``analyze()`` is pure (snapshot + config → result). ``ProfileAnalysisService`` builds the
snapshot from the database, runs it, and replaces the user's derived rows in one transaction,
so a failure leaves the previous profile untouched. Analysis never calls GitHub.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from developers.models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    Interest,
    InterestEvidence,
    Skill,
    SkillEvidence,
)
from github.models import GitHubProfile
from repositories.models import Repository, UserRepository
from services.errors import PermanentJobError

from .collectors import contribution_skills, dependency_skills, language_skills, topic_skills
from .confidence import compute_confidence
from .experience import estimate_experience, experience_signals
from .inputs import ContributionInput, DependencyInput, Evidence, ProfileInput, RepoInput
from .interests import DetectedInterest, detect_interests
from .languages import LanguageShare, aggregate_languages
from .readme import readme_skills
from .summary import build_summary
from .taxonomy import INTERESTS_BY_SLUG, SKILLS_BY_SLUG, TAXONOMY_VERSION

logger = logging.getLogger(__name__)

# Skills at or above this confidence count as "well evidenced" for experience estimation.
WELL_EVIDENCED = 0.5
SUMMARY_CATEGORIES = ("framework", "library")
MARKUP = frozenset({"html", "css"})


class ProfileAnalysisError(PermanentJobError):
    code = "analysis_failed"


@dataclass(frozen=True)
class AnalysisConfig:
    evidence_weights: dict[str, float]
    interest_weights: dict[str, float]
    decay: float
    cap: float
    language_min_share: float
    repeated_contribution_min_prs: int
    interest_min_strength: float
    experience_thresholds: dict[str, list[float]]
    taxonomy_version: str = TAXONOMY_VERSION

    @classmethod
    def from_settings(cls) -> AnalysisConfig:
        return cls(
            evidence_weights=dict(settings.EVIDENCE_WEIGHTS),
            interest_weights=dict(settings.INTEREST_EVIDENCE_WEIGHTS),
            decay=settings.EVIDENCE_REPEAT_DECAY,
            cap=settings.CONFIDENCE_CAP,
            language_min_share=settings.LANGUAGE_MIN_SHARE,
            repeated_contribution_min_prs=settings.REPEATED_CONTRIBUTION_MIN_PRS,
            interest_min_strength=settings.INTEREST_MIN_STRENGTH,
            experience_thresholds={k: list(v) for k, v in settings.EXPERIENCE_THRESHOLDS.items()},
        )


@dataclass(frozen=True)
class DetectedSkill:
    slug: str
    confidence: float
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class AnalysisResult:
    skills: list[DetectedSkill]
    interests: list[DetectedInterest]
    languages: list[LanguageShare]
    experience_level: str
    experience_signals: dict[str, Any]
    summary: str


def _observed_range(evidence: tuple[Evidence, ...]) -> tuple[datetime | None, datetime | None]:
    seen = sorted(e.observed_at for e in evidence if e.observed_at is not None)
    return (seen[0], seen[-1]) if seen else (None, None)


def analyze(profile: ProfileInput, config: AnalysisConfig) -> AnalysisResult:
    evidence = [
        *readme_skills(profile.readme, profile.readme_observed_at),
        *language_skills(profile, config.language_min_share),
        *topic_skills(profile),
        *dependency_skills(profile),
        *contribution_skills(
            profile, config.language_min_share, config.repeated_contribution_min_prs
        ),
    ]
    grouped: dict[str, list[Evidence]] = defaultdict(list)
    for item in evidence:
        if item.key in SKILLS_BY_SLUG:
            grouped[item.key].append(item)
    skills = sorted(
        (
            DetectedSkill(
                slug,
                compute_confidence(
                    items, config.evidence_weights, decay=config.decay, cap=config.cap
                ),
                tuple(items),
            )
            for slug, items in grouped.items()
        ),
        key=lambda s: (-s.confidence, SKILLS_BY_SLUG[s.slug].name.lower()),
    )

    interests = detect_interests(
        profile,
        config.interest_weights,
        decay=config.decay,
        cap=config.cap,
        min_strength=config.interest_min_strength,
    )
    languages = aggregate_languages(profile)
    well_evidenced = sum(1 for s in skills if s.confidence >= WELL_EVIDENCED)
    level, audit = estimate_experience(
        experience_signals(profile, well_evidenced), config.experience_thresholds
    )
    # "Works mostly in / frequently uses" needs evidence of use, not only a README mention.
    # Languages rank by confidence, not bytes: notebooks and markup inflate byte counts.
    used = [s for s in skills if any(e.source != "readme" for e in s.evidence)]
    summary = build_summary(
        [
            SKILLS_BY_SLUG[s.slug].name
            for s in used
            if SKILLS_BY_SLUG[s.slug].category == "language" and s.slug not in MARKUP
        ],
        [
            SKILLS_BY_SLUG[s.slug].name
            for s in used
            if SKILLS_BY_SLUG[s.slug].category in SUMMARY_CATEGORIES
        ],
        [INTERESTS_BY_SLUG[i.slug].name for i in interests],
    )
    return AnalysisResult(skills, interests, languages, level, audit, summary)


# --- snapshot -------------------------------------------------------------------------------


def _repo_input(repo: Repository) -> RepoInput:
    return RepoInput(
        id=repo.pk,
        full_name=repo.full_name,
        description=repo.description,
        primary_language=repo.primary_language,
        languages={lang.language: lang.bytes for lang in repo.languages.all()},
        topics=tuple(t.topic for t in repo.topics.all()),
        dependencies=tuple(
            DependencyInput(d.ecosystem, d.name, d.manifest_path) for d in repo.dependencies.all()
        ),
        pushed_at=repo.pushed_at,
        is_fork=repo.is_fork,
    )


def build_input(user: User, now: datetime) -> ProfileInput:
    github = GitHubProfile.objects.filter(user=user).first()
    owned = (
        Repository.objects.filter(
            user_links__user=user, user_links__relation=UserRepository.Relation.OWNER
        )
        .prefetch_related("languages", "topics", "dependencies")
        .order_by("-pushed_at", "pk")
        .distinct()
    )
    contributed = (
        UserRepository.objects.filter(user=user, relation=UserRepository.Relation.CONTRIBUTOR)
        .select_related("repository")
        .prefetch_related("repository__languages", "repository__topics", "repository__dependencies")
        .order_by("repository__full_name")
    )
    return ProfileInput(
        now=now,
        readme=github.profile_readme if github and github.has_profile_readme else "",
        readme_observed_at=github.synced_at if github else None,
        account_created_at=github.github_created_at if github else None,
        owned=tuple(_repo_input(repo) for repo in owned),
        contributions=tuple(
            ContributionInput(
                repo=_repo_input(link.repository),
                merged_pr_count=link.merged_pr_count or 0,
                push_count=link.push_count or 0,
                last_contributed_at=link.last_contributed_at,
            )
            for link in contributed
        ),
    )


# --- persistence ----------------------------------------------------------------------------


def _upsert_catalog_skills(slugs: list[str]) -> dict[str, Skill]:
    Skill.objects.bulk_create(
        [
            Skill(slug=slug, name=SKILLS_BY_SLUG[slug].name, category=SKILLS_BY_SLUG[slug].category)
            for slug in slugs
        ],
        update_conflicts=True,
        unique_fields=["slug"],
        update_fields=["name", "category"],
    )
    return Skill.objects.in_bulk(slugs, field_name="slug")


def _upsert_catalog_interests(slugs: list[str]) -> dict[str, Interest]:
    Interest.objects.bulk_create(
        [Interest(slug=slug, name=INTERESTS_BY_SLUG[slug].name) for slug in slugs],
        update_conflicts=True,
        unique_fields=["slug"],
        update_fields=["name"],
    )
    return Interest.objects.in_bulk(slugs, field_name="slug")


class ProfileAnalysisService:
    def __init__(self, user: User, config: AnalysisConfig | None = None) -> None:
        self.user = user
        self.config = config or AnalysisConfig.from_settings()

    def run(self) -> DeveloperProfile:
        try:
            now = timezone.now()
            result = analyze(build_input(self.user, now), self.config)
            return self._persist(result, now)
        except Exception as exc:
            logger.exception("Profile analysis failed for user %s", self.user.pk)
            raise ProfileAnalysisError(type(exc).__name__) from exc

    @transaction.atomic
    def _persist(self, result: AnalysisResult, now: datetime) -> DeveloperProfile:
        profile, _ = DeveloperProfile.objects.select_for_update().get_or_create(
            user=self.user, defaults={"analyzed_at": now}
        )
        # Preferences are left alone: the user will own them once they can edit them.
        profile.summary = result.summary
        profile.experience_level = result.experience_level
        profile.experience_signals = result.experience_signals
        profile.languages = list(result.languages)
        profile.analysis_config = asdict(self.config)
        profile.analyzed_at = now
        profile.save()

        profile.skills.all().delete()
        profile.interests.all().delete()

        catalog_skills = _upsert_catalog_skills([s.slug for s in result.skills])
        developer_skills = DeveloperSkill.objects.bulk_create(
            [
                DeveloperSkill(
                    profile=profile,
                    skill=catalog_skills[s.slug],
                    confidence=s.confidence,
                    first_observed_at=first,
                    last_observed_at=last,
                )
                for s in result.skills
                for first, last in [_observed_range(s.evidence)]
            ]
        )
        SkillEvidence.objects.bulk_create(
            SkillEvidence(
                developer_skill=developer_skill,
                source=e.source,
                repository_id=e.repository_id,
                detail=e.detail[:255],
                observed_at=e.observed_at,
            )
            for developer_skill, detected in zip(developer_skills, result.skills, strict=True)
            for e in detected.evidence
        )

        catalog_interests = _upsert_catalog_interests([i.slug for i in result.interests])
        developer_interests = DeveloperInterest.objects.bulk_create(
            [
                DeveloperInterest(
                    profile=profile, interest=catalog_interests[i.slug], strength=i.strength
                )
                for i in result.interests
            ]
        )
        InterestEvidence.objects.bulk_create(
            InterestEvidence(
                developer_interest=developer_interest,
                source=e.source,
                repository_id=e.repository_id,
                detail=e.detail[:255],
                observed_at=e.observed_at,
            )
            for developer_interest, detected in zip(
                developer_interests, result.interests, strict=True
            )
            for e in detected.evidence
        )
        return profile
