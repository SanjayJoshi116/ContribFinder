"""Review sweep of `services/profiling/` (Bug_Backlog.md batch 43, PROF-1…PROF-9)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from developers.models import DeveloperProfile, Skill
from services.issues.technologies import detect
from services.profiling.analysis import ProfileAnalysisService
from services.profiling.collectors import contribution_skills
from services.profiling.experience import experience_signals
from services.profiling.interests import SYNONYM_MATCHER, interest_evidence
from services.profiling.manifests import (
    parse_gradle,
    parse_pom,
    parse_pyproject,
    parse_requirements,
)
from services.profiling.readme import ALL_MATCHER, PLAIN_MATCHER, readme_skills, tech_sections
from services.profiling.taxonomy import TAXONOMY_VERSION

from .profiling_fixtures import contribution, profile


def readme(text: str) -> dict[str, str]:
    """README evidence as analysis computes it: from the README stored on ``ProfileInput``."""
    return {e.key: e.detail for e in readme_skills(profile(readme=text).readme, None)}


# --- PROF-1: case-fold matching -------------------------------------------------------------


# Code points keep the look-alike letters visible: dotless i, long s, Kelvin sign, dotted capital I.
DOTLESS_I, LONG_S, KELVIN, DOTTED_I = chr(0x131), chr(0x17F), chr(0x212A), chr(0x130)


@pytest.mark.parametrize(
    "text",
    [
        f"Kotl{DOTLESS_I}n developer",
        f"Mach{DOTLESS_I}ne learning",
        f"{LONG_S}cala",
        f"{KELVIN}otlin",
        f"{DOTTED_I}stanbul",
    ],
)
def test_case_variants_never_raise(text: str) -> None:
    for matcher in (PLAIN_MATCHER, ALL_MATCHER, SYNONYM_MATCHER):
        matcher.find(text)


def test_case_variants_map_back_to_their_phrase() -> None:
    assert set(ALL_MATCHER.find(f"{LONG_S}cala and {KELVIN}otlin")) == {"scala", "kotlin"}


def test_issue_text_with_a_case_variant_is_analyzed() -> None:
    detect(f"F{DOTLESS_I}x the Python parser", [], f"Mach{DOTLESS_I}ne learning body")


# --- PROF-2, PROF-3, PROF-7: README ---------------------------------------------------------


def test_commented_out_section_gives_no_evidence() -> None:
    assert readme("<!--\n## Tech stack\n- Go\n- Rust\n-->") == {}


def test_badge_inside_a_comment_gives_no_evidence() -> None:
    assert readme("<!-- ![x](https://img.shields.io/badge/x-y-z?logo=postgresql) -->") == {}


def test_comment_in_a_fence_is_not_a_heading() -> None:
    text = "## About\n```bash\n# install tools\ngo run .\n```\nI like rust."
    assert [title for title, _ in tech_sections(text)] == []
    assert readme(text) == {}


def test_fence_does_not_split_a_skills_section() -> None:
    found = readme("## Skills\n- Python\n```sh\n# setup\n```\n- Go")
    assert found == {"python": '"Skills" section', "go": '"Skills" section'}


def test_technologies_in_a_fence_inside_a_skills_section_count() -> None:
    assert set(readme("## Skills\n```\nrust go\n```")) == {"rust", "go"}


def test_heading_keeps_a_trailing_hash_of_a_word() -> None:
    assert readme("## Languages: C#\n- C#") == {"csharp": '"Languages C#" section'}
    assert [title for title, _ in tech_sections("## Skills ##\nPython")] == ["Skills"]


# --- PROF-4, PROF-5, PROF-6: manifests ------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        '[project]\noptional-dependencies={dev="pytest"}',
        '[project]\ndependencies="django"',
        '[dependency-groups]\ndev="pytest"',
        "project = 1",
    ],
)
def test_pyproject_values_of_the_wrong_type_name_nothing(text: str) -> None:
    assert parse_pyproject(text) == []


def test_pyproject_valid_groups_unchanged() -> None:
    text = '[project]\ndependencies=["django>=4"]\n[project.optional-dependencies]\ndev=["pytest"]'
    assert parse_pyproject(text) == ["django", "pytest"]


def test_requirements_direct_references_keep_their_name() -> None:
    text = (
        "django @ https://example.com/django.whl\n"
        "requests[socks] @ git+https://example.com/requests\n"
        "flask\n"
        "https://example.com/bare.whl\n"
        "-e git+https://example.com/editable\n"
    )
    assert parse_requirements(text) == ["django", "requests", "flask"]


def test_pom_comments_are_ignored() -> None:
    text = (
        "<!-- <dependency><groupId>org.springframework.boot</groupId>"
        "<artifactId>spring-boot-starter-web</artifactId></dependency> -->"
        "<dependency><groupId>c</groupId><artifactId>d</artifactId></dependency>"
    )
    assert parse_pom(text) == ["c:d"]


def test_gradle_comments_are_ignored_and_urls_kept() -> None:
    text = (
        '// implementation "org.springframework.boot:spring-boot-starter-web:3.0"\n'
        '/* api("p:q:1") */\n'
        'implementation "org.ok:lib:1" // a note\n'
        'maven { url "https://repo.example.com" }\n'
        'implementation("a.b:c:2")\n'
    )
    assert parse_gradle(text) == ["org.ok:lib", "a.b:c"]


# --- PROF-8: forks ---------------------------------------------------------------------------


def test_contributions_to_forks_give_no_evidence() -> None:
    fork = contribution(
        prs=2, pushes=3, is_fork=True, languages={"Rust": 100}, topics=("security",)
    )
    forked = profile(contributions=(fork,))
    assert contribution_skills(forked, 0.1, 3) == []
    assert [e for e in interest_evidence(forked) if e.source == "contribution"] == []


def test_non_fork_contribution_unchanged() -> None:
    c = contribution(prs=1, languages={"Rust": 100}, topics=("security",))
    found = profile(contributions=(c,))
    assert {e.key for e in contribution_skills(found, 0.1, 3)} == {"rust"}
    assert {e.key for e in interest_evidence(found) if e.source == "contribution"} == {"security"}


def test_experience_ignores_fork_contributions() -> None:
    fork = contribution(prs=2, pushes=1, is_fork=True, languages={"Rust": 100})
    kept = contribution(prs=1, languages={"Go": 100})
    signals = experience_signals(profile(contributions=(fork, kept)), 0)
    assert signals["merged_external_prs"] == 1
    assert signals["contributed_repositories"] == 1


# --- Fix-diff review: unterminated comments, fences, Gradle strings ---------------------------


def test_unterminated_comment_hides_the_rest_of_the_readme() -> None:
    assert readme("## Skills\n- Python\n<!--\n## Tech stack\n- Go\n- Rust") == {
        "python": '"Skills" section'
    }


def test_unterminated_comment_in_an_issue_body_is_not_description() -> None:
    from services.profiling.text import strip_html_comments

    assert strip_html_comments("Short.<!-- template\nlong instructions") == "Short."


def test_nested_longer_fence_hides_inner_fences() -> None:
    text = (
        "## Usage\n````markdown\n```bash\n# install tools\npip install rust go\n```\n````\n"
        "## Skills\n- Go"
    )
    assert [title for title, _ in tech_sections(text)] == ["Skills"]


def test_fence_with_an_info_string_does_not_close() -> None:
    text = "## About\n```\n```js\n# not a heading\n```\n## Tools\n- Docker"
    assert [title for title, _ in tech_sections(text)] == ["Tools"]


def test_gradle_globs_and_urls_in_strings_are_not_comments() -> None:
    text = (
        "packagingOptions { exclude 'META-INF/*.kotlin_module' }\n"
        "dependencies { implementation 'androidx.core:core-ktx:1.9.0' }\n"
        "include '**/*.java'\n"
        "maven { url 'https://repo.example.com' }\n"
        "/* legacy */ api('ok:one:2')\n"
    )
    assert parse_gradle(text) == ["androidx.core:core-ktx", "ok:one"]


# --- PROF-9: catalog writes -------------------------------------------------------------------


@pytest.mark.django_db
def test_unchanged_catalog_is_not_rewritten(synced) -> None:
    ProfileAnalysisService(synced).run()
    with CaptureQueriesContext(connection) as ctx:
        ProfileAnalysisService(synced).run()
    updates = [
        q["sql"]
        for q in ctx.captured_queries
        if q["sql"].startswith("UPDATE")
        and ('"developers_skill"' in q["sql"] or '"developers_interest"' in q["sql"])
    ]
    assert updates == []


@pytest.mark.django_db
def test_renamed_catalog_entry_is_updated(synced) -> None:
    ProfileAnalysisService(synced).run()
    Skill.objects.filter(slug="python").update(name="Old name", category="tool")
    ProfileAnalysisService(synced).run()
    python = Skill.objects.get(slug="python")
    assert (python.name, python.category) == ("Python", "language")


@pytest.mark.django_db
def test_profile_records_the_taxonomy_version(synced) -> None:
    ProfileAnalysisService(synced).run()
    stored = DeveloperProfile.objects.get(user=synced)
    assert stored.analysis_config["taxonomy_version"] == TAXONOMY_VERSION == "2026.11.1"


def test_commented_out_readme_gives_no_interests() -> None:
    commented = profile(readme="<!-- I build machine learning pipelines -->")
    assert [e for e in interest_evidence(commented) if e.source == "readme"] == []
