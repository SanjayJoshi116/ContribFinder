"""Root-level dependency manifest parsers (design D4). Pure functions: text in, names out.

A manifest that cannot be parsed yields no dependencies rather than an error: one broken file
must not fail a sync or an analysis. pom.xml and Gradle files are read with regular expressions,
so no XML entity expansion can happen.
"""

from __future__ import annotations

import json
import logging
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .taxonomy import normalize_dependency
from .text import strip_html_comments

logger = logging.getLogger(__name__)


@dataclass(frozen=True, order=True)
class Dependency:
    ecosystem: str
    name: str


# PEP 508: the distribution name is the leading identifier.
_PEP508_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


# PEP 508 direct reference: "name[extras] @ URL" names its package (PROF-5).
_PEP508_DIRECT = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*@\s*\S")


def _pep508_names(specs: object) -> list[str]:
    """Names from a list of PEP 508 strings; any other value names nothing (PROF-4: a string
    would otherwise be read one character at a time)."""
    if not isinstance(specs, list):
        return []
    names = []
    for spec in specs:
        if isinstance(spec, str) and (match := _PEP508_NAME.match(spec)):
            names.append(match.group(1))
    return names


def _table(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_requirements(text: str) -> list[str]:
    names = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if match := _PEP508_DIRECT.match(line):
            names.append(match.group(1))
            continue
        if not line or line.startswith("-") or "://" in line or line.startswith((".", "/")):
            continue
        if match := _PEP508_NAME.match(line):
            names.append(match.group(1))
    return names


def parse_pyproject(text: str) -> list[str]:
    data = tomllib.loads(text)
    project = _table(data.get("project"))
    names = _pep508_names(project.get("dependencies", []))
    for group in _table(project.get("optional-dependencies")).values():
        names += _pep508_names(group)
    for group in _table(data.get("dependency-groups")).values():
        names += _pep508_names(group)  # include-group tables are skipped (not strings)
    poetry = _table(_table(data.get("tool")).get("poetry"))
    poetry_tables = [_table(poetry.get("dependencies")), _table(poetry.get("dev-dependencies"))]
    poetry_tables += [
        _table(_table(g).get("dependencies")) for g in _table(poetry.get("group")).values()
    ]
    for table in poetry_tables:
        names += [name for name in table if name.lower() != "python"]
    return names


def parse_package_json(text: str) -> list[str]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("package.json is not an object")
    names: list[str] = []
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key) or {}
        if isinstance(section, dict):
            names += [str(name) for name in section]
    return names


_GO_REQUIRE_LINE = re.compile(r"^\s*require\s+([^\s()]+)\s+\S+", re.MULTILINE)
_GO_REQUIRE_BLOCK = re.compile(r"^\s*require\s*\((.*?)^\s*\)", re.MULTILINE | re.DOTALL)


def parse_go_mod(text: str) -> list[str]:
    names = _GO_REQUIRE_LINE.findall(text)
    for block in _GO_REQUIRE_BLOCK.findall(text):
        for line in block.splitlines():
            line = line.split("//", 1)[0].strip()
            if line:
                names.append(line.split()[0])
    return names


def parse_cargo_toml(text: str) -> list[str]:
    data = tomllib.loads(text)
    tables: list[Any] = [
        data.get(key, {}) for key in ("dependencies", "dev-dependencies", "build-dependencies")
    ]
    tables.append(data.get("workspace", {}).get("dependencies", {}))
    names: list[str] = []
    for table in tables:
        for name, spec in table.items():
            # `alias = { package = "real-name", ... }` depends on real-name.
            if isinstance(spec, dict) and isinstance(spec.get("package"), str):
                names.append(spec["package"])
            else:
                names.append(name)
    return names


_POM_DEPENDENCY = re.compile(r"<dependency>(.*?)</dependency>", re.DOTALL)
_POM_GROUP = re.compile(r"<groupId>\s*([^<\s]+)\s*</groupId>")
_POM_ARTIFACT = re.compile(r"<artifactId>\s*([^<\s]+)\s*</artifactId>")


# Gradle comments (PROF-6), outside string literals only: a string keeps its "//" (URLs) and
# "/*" (globs such as 'META-INF/*.kotlin_module'), so a match of the first alternative is
# put back and only the comment alternatives are removed.
_GRADLE_COMMENT = re.compile(
    r"""("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|/\*.*?(?:\*/|\Z)|//[^\n]*""", re.S
)


def _strip_gradle_comments(text: str) -> str:
    return _GRADLE_COMMENT.sub(lambda m: m.group(1) or "", text)


def parse_pom(text: str) -> list[str]:
    names = []
    for block in _POM_DEPENDENCY.findall(strip_html_comments(text)):
        group, artifact = _POM_GROUP.search(block), _POM_ARTIFACT.search(block)
        if group and artifact:
            names.append(f"{group.group(1)}:{artifact.group(1)}")
    return names


# implementation("group:artifact:version"), testImplementation 'group:artifact', api(...)
_GRADLE_COORD = re.compile(
    r"""\b(?:implementation|api|compileOnly|runtimeOnly|testImplementation|
    testRuntimeOnly|annotationProcessor|kapt|ksp|compile|testCompile)\b\s*\(?\s*
    (?:platform\(\s*)?["']([\w.\-]+):([\w.\-]+)(?::[^"']*)?["']""",
    re.VERBOSE,
)


def parse_gradle(text: str) -> list[str]:
    text = _strip_gradle_comments(text)
    return [f"{group}:{artifact}" for group, artifact in _GRADLE_COORD.findall(text)]


MANIFESTS: dict[str, tuple[str, Callable[[str], list[str]]]] = {
    "requirements.txt": ("pypi", parse_requirements),
    "pyproject.toml": ("pypi", parse_pyproject),
    "package.json": ("npm", parse_package_json),
    "go.mod": ("go", parse_go_mod),
    "Cargo.toml": ("cargo", parse_cargo_toml),
    "pom.xml": ("maven", parse_pom),
    "build.gradle": ("gradle", parse_gradle),
    "build.gradle.kts": ("gradle", parse_gradle),
}


def is_manifest(filename: str) -> bool:
    return filename in MANIFESTS


def parse_manifest(filename: str, text: str) -> list[Dependency]:
    """Dependencies declared in a supported root manifest; ``[]`` if unsupported or invalid."""
    if filename not in MANIFESTS:
        return []
    ecosystem, parser = MANIFESTS[filename]
    try:
        names = parser(text)
    # RecursionError: nesting too deep for the JSON/TOML parsers (untrusted input).
    except (ValueError, TypeError, AttributeError, RecursionError, tomllib.TOMLDecodeError):
        logger.debug("Could not parse manifest %s", filename)
        return []
    deps = {Dependency(ecosystem, normalize_dependency(ecosystem, n)) for n in names if n}
    return sorted(deps)
