"""Setup facts of a repository (spec: repository-analysis "Repository data collection"; change
setup-readiness, design D3). Pure: reads directory entries, fetches nothing.

Only the root and ``.github/workflows`` are looked at, so a fact not found means only that no
marker matched there (tests kept next to the code are not seen). Facts are shown, never scored.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from services.github.client import ContentEntry

DIR, FILE = "dir", "file"

# Root CI configuration of services other than GitHub Actions.
CI_FILES = frozenset(
    {
        ".gitlab-ci.yml",
        ".travis.yml",
        "azure-pipelines.yml",
        "jenkinsfile",
        ".drone.yml",
        "appveyor.yml",
        "bitbucket-pipelines.yml",
        ".cirrus.yml",
    }
)
CI_DIRS = frozenset({".circleci", ".buildkite"})
WORKFLOW_SUFFIXES = (".yml", ".yaml")
GITHUB_DIR = ".github"
WORKFLOWS_PATH = ".github/workflows"

TEST_DIRS = frozenset({"test", "tests", "spec", "specs", "__tests__", "testing"})
TEST_FILES = frozenset(
    {
        "pytest.ini",
        "tox.ini",
        "noxfile.py",
        "conftest.py",
        "phpunit.xml",
        "phpunit.xml.dist",
        ".rspec",
        "karma.conf.js",
    }
)
TEST_FILE_PREFIXES = ("jest.config.", "vitest.config.", "playwright.config.", "cypress.config.")

DEV_ENVIRONMENT_DIRS = frozenset({".devcontainer"})
DEV_ENVIRONMENT_FILES = frozenset({".devcontainer.json", ".gitpod.yml"})

COMPOSE_FILES = frozenset(
    {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
)


@dataclass(frozen=True)
class SetupFacts:
    ci: bool
    tests: bool
    dev_environment: bool
    docker_compose: bool


def _names(entries: Sequence[ContentEntry], kind: str) -> set[str]:
    return {e.name.lower() for e in entries if e.type == kind}


def _root_ci(root: Sequence[ContentEntry]) -> bool:
    return bool(_names(root, FILE) & CI_FILES or _names(root, DIR) & CI_DIRS)


def needs_workflows(root: Sequence[ContentEntry]) -> bool:
    """Whether ``.github/workflows`` must be listed to decide CI: the root has a ``.github``
    directory and no CI configuration of another service."""
    return GITHUB_DIR in _names(root, DIR) and not _root_ci(root)


def detect(
    root: Sequence[ContentEntry], workflows: Sequence[ContentEntry] | None = None
) -> SetupFacts:
    """``workflows``: the entries of ``.github/workflows`` when they were listed."""
    files, dirs = _names(root, FILE), _names(root, DIR)
    workflow_files = _names(workflows or (), FILE)
    return SetupFacts(
        ci=_root_ci(root) or any(name.endswith(WORKFLOW_SUFFIXES) for name in workflow_files),
        tests=bool(
            dirs & TEST_DIRS
            or files & TEST_FILES
            or any(name.startswith(TEST_FILE_PREFIXES) for name in files)
        ),
        dev_environment=bool(dirs & DEV_ENVIRONMENT_DIRS or files & DEV_ENVIRONMENT_FILES),
        docker_compose=bool(files & COMPOSE_FILES),
    )
