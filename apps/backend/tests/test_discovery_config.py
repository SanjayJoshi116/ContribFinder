import pytest
from django.conf import settings
from django.test import override_settings

from core.checks import discovery_config_check

from .checks_helpers import ids


def test_default_config_is_valid() -> None:
    assert discovery_config_check() == []


@pytest.mark.parametrize(
    "name", ["DISCOVERY_MAX_QUERIES", "DISCOVERY_MAX_POOL", "REPO_REFRESH_BATCH"]
)
@pytest.mark.parametrize("value", [0, -1, "10"])
def test_budgets_and_caps_must_be_positive(name: str, value: object) -> None:
    with override_settings(**{name: value}):
        assert "core.E020" in ids(discovery_config_check())


def test_results_per_query_limited_to_one_page() -> None:
    with override_settings(DISCOVERY_RESULTS_PER_QUERY=101):
        assert "core.E021" in ids(discovery_config_check())


@pytest.mark.parametrize(
    "shares",
    [
        {**settings.DISCOVERY_QUERY_SHARES, "semantic": 1},
        {k: v for k, v in settings.DISCOVERY_QUERY_SHARES.items() if k != "topic"},
        {**settings.DISCOVERY_QUERY_SHARES, "skill": -1},
    ],
    ids=["unknown", "missing", "negative"],
)
def test_invalid_query_shares_rejected(shares) -> None:
    with override_settings(DISCOVERY_QUERY_SHARES=shares):
        assert "core.E022" in ids(discovery_config_check())


def test_unknown_stale_part_rejected() -> None:
    with override_settings(REPO_STALE_AFTER={**settings.REPO_STALE_AFTER, "pulls": 1}):
        assert "core.E023" in ids(discovery_config_check())


@pytest.mark.parametrize(
    "override",
    [
        {"moderate_push_days": 10},  # stricter than recent_push_days=30
        {"moderate_commits": 50},
        {"moderate_merged_prs": 9},
        {"recent_commits": "ten"},
    ],
)
def test_inconsistent_activity_thresholds_rejected(override) -> None:
    with override_settings(ACTIVITY_THRESHOLDS={**settings.ACTIVITY_THRESHOLDS, **override}):
        assert "core.E024" in ids(discovery_config_check())


@pytest.mark.parametrize(
    ("bands", "message"),
    [
        ([], "non-empty list"),
        ([[20, None], [1000, None]], "only the last band"),
        ([[20, 999], [500, None]], "ascending"),
        ([[20, 10]], "at least its low"),
        ([[20]], "band 0 must be"),
        ([[30, None]], "first band must start"),
        ([[20, 99], [100, 999], [1000, None]], "at least the number of bands"),
    ],
)
def test_invalid_star_bands_rejected(bands, message: str) -> None:
    with override_settings(DISCOVERY_STAR_BANDS=bands, DISCOVERY_MAX_QUERIES=2):
        errors = [m for m in discovery_config_check() if m.id == "core.E025"]
        assert errors and message in errors[0].msg


def test_single_open_band_is_valid() -> None:
    with override_settings(DISCOVERY_STAR_BANDS=[[20, None]], DISCOVERY_MAX_QUERIES=10):
        assert discovery_config_check() == []


@pytest.mark.parametrize("topics", ["awesome", ["awesome", ""], [1]])
def test_invalid_excluded_topics_rejected(topics) -> None:
    with override_settings(DISCOVERY_EXCLUDED_TOPICS=topics):
        assert "core.E026" in ids(discovery_config_check())
