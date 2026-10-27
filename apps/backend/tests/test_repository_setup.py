"""Setup facts from directory entries (change setup-readiness, group 1). Pure: no database."""

import pytest

from services.github.client import ContentEntry
from services.repositories.setup import SetupFacts, detect, needs_workflows


def entries(*names: str) -> list[ContentEntry]:
    """``name/`` is a directory, anything else a file."""
    return [ContentEntry(n.rstrip("/"), "dir" if n.endswith("/") else "file", 0) for n in names]


NONE = SetupFacts(ci=False, tests=False, dev_environment=False, docker_compose=False)


def test_empty_root_finds_nothing() -> None:
    assert detect([]) == NONE
    assert detect(entries("README.md", "main.go", "src/")) == NONE


def test_all_four_found() -> None:
    root = entries(".github/", "tests/", ".devcontainer/", "docker-compose.yml")
    assert detect(root, entries("ci.yml")) == SetupFacts(True, True, True, True)


@pytest.mark.parametrize(
    "names",
    [
        (".gitlab-ci.yml",),
        (".travis.yml",),
        ("azure-pipelines.yml",),
        ("Jenkinsfile",),
        (".circleci/",),
        (".buildkite/",),
    ],
)
def test_root_ci_of_another_service(names) -> None:
    assert detect(entries(*names)).ci is True


@pytest.mark.parametrize(
    ("workflows", "found"),
    [
        (("ci.yml",), True),
        (("release.yaml", "README.md"), True),
        (("README.md",), False),
        ((), False),
        (("deploy.yml/",), False),  # a directory named like a workflow
    ],
)
def test_github_actions_workflows(workflows, found: bool) -> None:
    assert detect(entries(".github/"), entries(*workflows)).ci is found


def test_github_dir_without_listing_is_not_ci() -> None:
    assert detect(entries(".github/")).ci is False


def test_needs_workflows_only_for_a_github_dir_without_other_ci() -> None:
    assert needs_workflows(entries(".github/")) is True
    assert needs_workflows(entries(".github/", ".travis.yml")) is False
    assert needs_workflows(entries(".github")) is False  # a file, not a directory
    assert needs_workflows(entries("src/")) is False


@pytest.mark.parametrize(
    "name",
    [
        "tests/",
        "test/",
        "spec/",
        "__tests__/",
        "Tests/",
        "pytest.ini",
        "tox.ini",
        "conftest.py",
        "phpunit.xml.dist",
        "jest.config.ts",
        "vitest.config.mjs",
        "playwright.config.ts",
    ],
)
def test_tests(name: str) -> None:
    assert detect(entries(name)).tests is True


@pytest.mark.parametrize("name", ["tests", "testdata/", "contest.py", "jest.json"])
def test_not_tests(name: str) -> None:
    # "tests" as a file, a near-miss directory or file name.
    assert detect(entries(name)).tests is False


@pytest.mark.parametrize("name", [".devcontainer/", ".devcontainer.json", ".gitpod.yml"])
def test_dev_environment(name: str) -> None:
    assert detect(entries(name)).dev_environment is True


def test_devcontainer_file_named_like_the_dir_is_not_enough() -> None:
    assert detect(entries(".devcontainer")).dev_environment is False


@pytest.mark.parametrize(
    "name", ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "Compose.yaml"]
)
def test_docker_compose(name: str) -> None:
    assert detect(entries(name)).docker_compose is True


def test_dockerfile_alone_is_not_compose() -> None:
    assert detect(entries("Dockerfile", "docker/")).docker_compose is False
