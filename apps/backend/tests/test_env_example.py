"""`.env.example` lists every setting the backend reads (ROOT-7), and the development settings
honor `DJANGO_DEBUG` (ROOT-6). Bug_Backlog.md batch 70."""

import ast
import importlib
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
TEMPLATE = BACKEND.parents[1] / ".env.example"
SETTINGS = [BACKEND / "config" / "settings" / name for name in ("base.py", "production.py")]
# Read by the test configuration only (config/settings/test.py), never set by a developer.
NOT_IN_TEMPLATE = {"DJANGO_READ_DOTENV"}
READERS = {"env_list", "env_words", "env_json", "env_mapping"}


def _reader(call: ast.Call) -> bool:
    """`env(...)`, `env.bool(...)` and friends, or one of the base.py helpers."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "env" or func.id in READERS
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and (func.value.id == "env")
    )


def _names_read(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and _reader(node) and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                names.add(first.value)
    return names


def test_the_template_lists_every_setting_read_from_the_environment() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    listed = set(re.findall(r"^#? ?([A-Z][A-Z0-9_]*)=", template, flags=re.MULTILINE))
    read = set().union(*(_names_read(path) for path in SETTINGS))
    assert read, "no settings found: the reader detection is broken"
    assert sorted(read - NOT_IN_TEMPLATE - listed) == []


@pytest.mark.parametrize(("value", "debug"), [("false", False), ("true", True), (None, True)])
def test_development_settings_honor_django_debug(
    monkeypatch: pytest.MonkeyPatch, value: str | None, debug: bool
) -> None:
    if value is None:
        monkeypatch.delenv("DJANGO_DEBUG", raising=False)
    else:
        monkeypatch.setenv("DJANGO_DEBUG", value)
    # Importing a settings module leaves django.conf.settings alone; base stays cached.
    module = importlib.import_module("config.settings.development")
    assert importlib.reload(module).DEBUG is debug
