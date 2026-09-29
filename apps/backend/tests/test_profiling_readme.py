from datetime import UTC, datetime

from services.profiling.readme import badge_skills, readme_skills, tech_sections
from services.profiling.text import PhraseMatcher

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def skills(readme: str) -> dict[str, str]:
    return {e.key: e.detail for e in readme_skills(readme, NOW)}


def test_tech_stack_section() -> None:
    found = skills("# Hi\nI build things.\n\n## Tech Stack\nPython, Django, React, Docker\n")
    assert {"python", "django", "react", "docker"} <= set(found)
    assert found["django"] == '"Tech Stack" section'


def test_one_evidence_per_skill_and_observed_at() -> None:
    evidence = readme_skills("## Skills\nPython\n\nI love Python. Python!", NOW)
    assert [e.key for e in evidence] == ["python"]
    assert evidence[0].source == "readme"
    assert evidence[0].observed_at == NOW
    assert evidence[0].repository_id is None


def test_section_ends_at_next_heading_of_same_level() -> None:
    readme = "## Skills\n### Backend\nGo\n## Hobbies\nI go hiking and rust old bikes\n"
    found = skills(readme)
    assert "go" in found
    assert "rust" not in found


def test_html_heading_section() -> None:
    readme = '<h3 align="left">Languages and Tools:</h3>\n<p>Rust, Spring</p>'
    assert {"rust", "spring"} <= set(skills(readme))


def test_bold_label_line() -> None:
    assert "go" in skills("**Languages:** Go, TypeScript\n\nOther text")


def test_shields_badges() -> None:
    readme = (
        "![](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql)"
        " ![Node](https://img.shields.io/badge/node.js-6DA55F?logo=node.js)"
        ' <img src="https://img.shields.io/badge/C%2B%2B-00599C?logo=c%2B%2B" />'
    )
    assert badge_skills(readme) >= {"postgresql", "nodejs", "cpp"}
    assert skills(readme)["postgresql"] == "Badge or skill icon"


def test_skill_icons_and_devicons() -> None:
    readme = (
        "[![My Skills](https://skillicons.dev/icons?i=go,rust,k8s,py)](https://skillicons.dev)\n"
        '<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/java/java-original.svg"'
        ' alt="java" width="40"/>'
    )
    assert {"go", "rust", "kubernetes", "python", "java"} <= badge_skills(readme)


def test_image_alt_text() -> None:
    assert "flask" in badge_skills('<img src="x.png" alt="Flask"/>')


def test_ambiguous_word_in_free_text_ignored() -> None:
    found = skills("# About\nI like to go hiking. Spring is my favourite season.")
    assert "go" not in found
    assert "spring" not in found


def test_unambiguous_alias_in_free_text() -> None:
    assert skills("I mostly write Django apps with Postgres.") == {
        "django": "Mentioned in text",
        "postgresql": "Mentioned in text",
    }


def test_unknown_term_ignored() -> None:
    assert skills("## Skills\nFooBarFramework") == {}


def test_no_readme() -> None:
    assert readme_skills("", None) == []
    assert readme_skills("   \n", NOW) == []


def test_tech_sections_titles() -> None:
    titles = [t for t, _ in tech_sections("## 🛠️ Tech Stack\nx\n## About\ny\n")]
    assert titles == ["Tech Stack"]


def test_phrase_matcher_boundaries() -> None:
    matcher = PhraseMatcher({"c": "c", "c++": "cpp", "c#": "csharp", "ai": "ai"})
    assert matcher.find("C, C++ and C#.") == {"c": "c", "cpp": "c++", "csharp": "c#"}
    assert matcher.find("maintain") == {}
    assert matcher.find("AI-powered") == {"ai": "ai"}
