"""Review sweep of ``recommendations/`` (Bug_Backlog.md batch 41, REC-1…REC-10)."""

import json
from pathlib import Path
from typing import Any

import pytest
from django.contrib.admin import site
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from developers.models import DeveloperProfile
from e2e.builders import make_candidate_repo
from feedback.models import DismissedRepository, RecommendationFeedback, SavedRepository
from recommendations.models import ImmutableConfig, Recommendation, ScoringConfig
from recommendations.serializers import readme_excerpt
from services.ranking.config import V2_PARAMS, V2_WEIGHTS

from .shared_fixtures import assert_changelist_flat, assert_view_only
from .test_evaluation_dataset import minimal
from .test_evaluation_sheet import export as sheet_export
from .test_models_phase5 import make_recommendation

pytestmark = pytest.mark.django_db


def recommendation(n: int) -> Recommendation:
    """One developer, repository, recommendation, save, dismissal and event per ``n``."""
    user = User.objects.create(username=f"dev{n}")
    profile = DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())
    repo = make_candidate_repo(2000 + n)
    rec = make_recommendation(profile, repo)
    SavedRepository.objects.create(user=user, repository=repo)
    DismissedRepository.objects.create(user=user, repository=make_candidate_repo(3000 + n))
    RecommendationFeedback.objects.create(
        user=user, recommendation=rec, repository=repo, action="viewed"
    )
    return rec


# --- View-only admins (REC-1, REC-6) ---------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    [Recommendation, RecommendationFeedback, SavedRepository, DismissedRepository],
    ids=lambda m: m.__name__,
)
def test_staff_cannot_add_change_or_delete(admin_user: User, model) -> None:
    assert_view_only(model, admin_user)


@pytest.mark.parametrize(
    "path",
    [
        "recommendations/recommendation",
        "feedback/recommendationfeedback",
        "feedback/savedrepository",
        "feedback/dismissedrepository",
    ],
)
def test_changelist_query_count_does_not_grow_with_rows(admin_client: Client, path: str) -> None:
    assert_changelist_flat(admin_client, f"/admin/{path}/", recommendation)


def test_read_only_admin_is_gone() -> None:
    import recommendations.admin as module

    assert not hasattr(module, "ReadOnlyAdmin")


# --- Scoring configurations in the admin (REC-2) ---------------------------------------------


def test_scoring_config_admin_cannot_add_or_delete(admin_user: User) -> None:
    request = RequestFactory().get("/admin/")
    request.user = admin_user
    config_admin = site._registry[ScoringConfig]
    active = ScoringConfig.objects.get(is_active=True)
    assert not config_admin.has_add_permission(request)
    assert not config_admin.has_delete_permission(request, active)
    assert config_admin.has_change_permission(request, active)


def test_active_config_cannot_be_deleted_through_the_admin(admin_client: Client) -> None:
    active = ScoringConfig.objects.get(is_active=True)
    url = f"/admin/recommendations/scoringconfig/{active.pk}/delete/"
    assert admin_client.post(url, {"post": "yes"}).status_code == 403
    assert ScoringConfig.objects.filter(pk=active.pk, is_active=True).exists()


def test_description_stays_editable_in_the_admin(admin_client: Client) -> None:
    config = ScoringConfig.objects.create(version="v3-admin", weights=V2_WEIGHTS, params=V2_PARAMS)
    url = f"/admin/recommendations/scoringconfig/{config.pk}/change/"
    response = admin_client.post(url, {"description": "Edited"})
    assert response.status_code == 302
    config.refresh_from_db()
    assert config.description == "Edited"
    assert config.weights == V2_WEIGHTS


# --- Save of a deleted configuration (REC-4) --------------------------------------------------


def test_deleted_config_is_not_inserted_again() -> None:
    config = ScoringConfig.objects.create(version="v3-gone", weights=V2_WEIGHTS, params=V2_PARAMS)
    ScoringConfig.objects.filter(pk=config.pk).delete()
    config.weights = {**V2_WEIGHTS, "skill": 0.30, "language": 0.20}
    with pytest.raises(ImmutableConfig):
        config.save()
    assert not ScoringConfig.objects.filter(version="v3-gone").exists()


# --- Top N (REC-3) ----------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "-5"])
def test_top_n_below_one_is_refused(tmp_path: Path, value: str) -> None:
    path = tmp_path / "mini.json"
    path.write_text(json.dumps(minimal()), encoding="utf-8")
    with pytest.raises(CommandError, match="--top-n must be at least 1"):
        call_command("evaluate_ranking", "--dataset", str(path), "--top-n", value)


# --- Judging commands (REC-7) -----------------------------------------------------------------


def _without_repository() -> dict[str, Any]:
    data = sheet_export()
    data["developers"][0]["candidates"][0].pop("repository")
    return data


@pytest.mark.parametrize(
    ("data", "message"),
    [([1, 2], "JSON object"), (_without_repository(), "no repository name")],
    ids=["list", "no-repository"],
)
def test_benchmark_sheet_refuses_malformed_exports(tmp_path: Path, data: Any, message: str) -> None:
    exported = tmp_path / "export.json"
    exported.write_text(json.dumps(data), encoding="utf-8")
    sheet = tmp_path / "sheet.csv"
    with pytest.raises(CommandError, match=message):
        call_command("benchmark_sheet", "--export", str(exported), "--out", str(sheet))
    assert not sheet.exists()


@pytest.mark.parametrize(
    ("data", "message"),
    [([1, 2], "JSON object"), (_without_repository(), "no repository name")],
    ids=["list", "no-repository"],
)
def test_import_judgments_refuses_malformed_exports(
    tmp_path: Path, data: Any, message: str
) -> None:
    exported = tmp_path / "export.json"
    exported.write_text(json.dumps(data), encoding="utf-8")
    sheet = tmp_path / "sheet.csv"
    sheet.write_text("repository,grade\nbench/a,1\n", encoding="utf-8")
    with pytest.raises(CommandError, match=message):
        call_command("import_judgments", "--export", str(exported), "--sheet", str(sheet))


# --- README excerpt (REC-8, REC-10) -----------------------------------------------------------


def test_excerpt_keeps_a_word_ending_at_the_limit() -> None:
    assert readme_excerpt("hello world foo", 11) == "hello world…"


def test_excerpt_still_cuts_one_long_word() -> None:
    assert readme_excerpt("abcdefghijkl", 5) == "abcde…"


def test_excerpt_keeps_word_characters_and_unescapes_entities() -> None:
    text = "Run pip install my_package, edit ~/.config. Tom &amp; Jerry, _emphasis_, ~~old~~."
    assert readme_excerpt(text, 500) == (
        "Run pip install my_package, edit ~/.config. Tom & Jerry, emphasis , old ."
    )


# --- Status endpoint (REC-9) ------------------------------------------------------------------


def test_status_runs_three_queries(api_client: APIClient) -> None:
    rec = recommendation(1)
    user = rec.developer.user
    api_client.force_authenticate(user)
    with CaptureQueriesContext(connection) as captured:
        body = api_client.get("/api/v1/recommendations/status").json()
    reads = [q for q in captured if "recommendations_recommendation" in q["sql"]]
    assert len(reads) == 2
    assert body["count"] == 1
    assert body["config_version"] == rec.scoring_config.version
    assert body["last_generated_at"] is not None
