"""Skill evidence from the profile README (spec: skill-detection, "README skill evidence").

Three places count, strongest first:
1. tech sections: headings such as "Skills", "Tech Stack", "Tools", "Languages"
   (Markdown or HTML headings, or a bold label line like "**Languages:** ...");
2. badges and skill icons: shields.io ``logo=`` and labels, image alt text, skillicons.dev,
   devicon URLs;
3. free text, for unambiguous aliases only.

Ambiguous aliases ("Go", "Rust", "Spring") are accepted in 1 and 2 only. A skill gets at most
one README evidence record.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlsplit

from .inputs import Evidence
from .taxonomy import AMBIGUOUS_PHRASES, PLAIN_PHRASES, skill_for_icon
from .text import PhraseMatcher, plain_text

SOURCE = "readme"

_SECTION_TITLE = re.compile(r"skill|tech|stack|tool|language|framework|technolog", re.I)
_ATX = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_HTML_HEADING = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.I | re.S)
_BOLD_LABEL = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*|__)([^*_]{1,60})(?:\*\*|__)\s*:?\s*(.*)$")
_TAG = re.compile(r"<[^>]+>")
_BADGE_USES = re.compile(r"\b(?:built|made|powered|written)\b", re.I)

_URLS = re.compile(r"https?://[^\s)\"'<>]+")
_MD_ALT = re.compile(r"!\[([^\]]*)\]")
_HTML_ALT = re.compile(r"<img[^>]*?\balt\s*=\s*[\"']([^\"']*)[\"']", re.I)
_DEVICON = re.compile(r"/icons/([\w.+#-]+)/[\w.+#-]+\.svg", re.I)

ALL_MATCHER = PhraseMatcher({**AMBIGUOUS_PHRASES, **PLAIN_PHRASES})
PLAIN_MATCHER = PhraseMatcher(PLAIN_PHRASES)


def _clean_title(title: str) -> str:
    title = _TAG.sub("", title)
    return re.sub(r"[^\w\s&/+#.-]", "", title).strip()[:60]


def tech_sections(readme: str) -> list[tuple[str, str]]:
    """``(title, text)`` for every skill/technology section of the README."""
    lines = readme.splitlines()
    headings: list[tuple[int, int, str]] = []  # (line index, level, title)
    for index, line in enumerate(lines):
        if match := _ATX.match(line):
            headings.append((index, len(match.group(1)), match.group(2)))
        elif match := _HTML_HEADING.search(line):
            headings.append((index, int(match.group(1)), match.group(2)))

    sections: list[tuple[str, str]] = []
    for position, (index, level, title) in enumerate(headings):
        if not _SECTION_TITLE.search(_TAG.sub("", title)):
            continue
        end = len(lines)
        for next_index, next_level, _ in headings[position + 1 :]:
            if next_level <= level:
                end = next_index
                break
        # An HTML heading may share its line with content after the closing tag.
        first = _HTML_HEADING.sub("", lines[index]) if not _ATX.match(lines[index]) else ""
        sections.append((_clean_title(title), "\n".join([first, *lines[index + 1 : end]])))

    # Bold label lines: "**Languages:** Python, Go" plus the lines right below it.
    for index, line in enumerate(lines):
        if (match := _BOLD_LABEL.match(line)) and _SECTION_TITLE.search(match.group(1)):
            body = [match.group(2)]
            for following in lines[index + 1 :]:
                if not following.strip() or _ATX.match(following):
                    break
                body.append(following)
            sections.append((_clean_title(match.group(1)), "\n".join(body)))
    return sections


def _shields_badge_skills(path: str) -> set[str]:
    """``<label>-<message>-<color>`` or ``<message>-<color>``; "--" is a literal dash. The label
    may name the skill; the message only when there is no label or the label introduces
    technologies ("language", "tech stack"), since messages are often free text ("code
    style-black", "platform-linux")."""
    segments = [
        unquote(segment.replace("\0", "-")).replace("_", " ")
        for segment in path.replace("--", "\0").split("-")
    ]
    if len(segments) > 1:
        segments.pop()  # the color
    message = segments.pop()
    label = segments[0] if segments else ""
    found = set(ALL_MATCHER.find(label))
    if not label.strip() or _SECTION_TITLE.search(label) or _BADGE_USES.search(label):
        found.update(ALL_MATCHER.find(message))
    return found


def badge_skills(readme: str) -> set[str]:
    """Skills named by badges, skill icons and image alt text."""
    found: set[str] = set()
    for url in _URLS.findall(readme):
        # URLs inside HTML attributes escape "&" as "&amp;".
        parts = urlsplit(html.unescape(url))
        host = parts.netloc.lower()
        query = parse_qs(parts.query)
        if host.endswith("shields.io"):
            for logo in query.get("logo", []):
                if slug := skill_for_icon(logo):
                    found.add(slug)
            if "/badge/" in parts.path:
                found.update(_shields_badge_skills(parts.path.split("/badge/", 1)[1]))
        elif host.endswith("skillicons.dev"):
            for icons in query.get("i", []):
                for token in icons.split(","):
                    if slug := skill_for_icon(token.strip()):
                        found.add(slug)
        elif "devicon" in url.lower() and (match := _DEVICON.search(parts.path)):
            if slug := skill_for_icon(match.group(1)):
                found.add(slug)
    for alt in [*_MD_ALT.findall(readme), *_HTML_ALT.findall(readme)]:
        found.update(ALL_MATCHER.find(alt))
    return found


def readme_skills(readme: str, observed_at: datetime | None) -> list[Evidence]:
    if not readme.strip():
        return []
    details: dict[str, str] = {}
    for title, text in tech_sections(readme):
        for slug in ALL_MATCHER.find(plain_text(text)):
            details.setdefault(slug, f'"{title}" section')
    for slug in sorted(badge_skills(readme)):
        details.setdefault(slug, "Badge or skill icon")
    for slug in PLAIN_MATCHER.find(plain_text(readme)):
        details.setdefault(slug, "Mentioned in text")
    return [Evidence(slug, SOURCE, None, detail, observed_at) for slug, detail in details.items()]
