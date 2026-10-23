from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

# Frozen copy of services/ranking/config.py V2_*: a migration must not change when that
# module does later.
WEIGHTS = {
    "skill": 0.35,
    "language": 0.15,
    "interest": 0.15,
    "framework": 0.10,
    "activity": 0.10,
    "openness": 0.05,
    "issue_fit": 0.05,
    "difficulty_fit": 0.05,
}
PARAMS = {
    "bands": {"strong": 0.55, "good": 0.35},
    "activity": {"recently_active": 1.0, "moderately_active": 0.6, "low_activity": 0.2},
    "openness": {
        "contributing": 0.4,
        "good_first_issue": 0.3,
        "help_wanted": 0.2,
        "issue_templates": 0.1,
    },
    "tech_sources": {"dependency": 1.0, "topic": 0.6},
    "issues": {
        "weights": {"technology": 0.6, "difficulty": 0.25, "approachability": 0.15},
        "min_score": 0.3,
        "per_recommendation": 5,
        "saturation": 3.0,
        "approachability": {"good_first_issue": 1.0, "help_wanted": 0.6},
        "difficulty_fit": {
            "beginner": {"beginner": 1.0, "intermediate": 0.5, "advanced": 0.0, "unknown": 0.3},
            "intermediate": {
                "beginner": 0.7,
                "intermediate": 1.0,
                "advanced": 0.5,
                "unknown": 0.4,
            },
            "experienced": {
                "beginner": 0.4,
                "intermediate": 0.8,
                "advanced": 1.0,
                "unknown": 0.5,
            },
            "unknown": {"beginner": 0.8, "intermediate": 0.7, "advanced": 0.4, "unknown": 0.4},
        },
    },
}
DESCRIPTION = (
    "v1 plus issue fit and difficulty fit (Phase 7). Experimental starting values, not product "
    "truth; change them only through a new version evaluated against benchmarks."
)


def seed(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    ScoringConfig = apps.get_model("recommendations", "ScoringConfig")
    # A stored v2 means a re-apply after a rollback that kept it: an operator had deactivated it
    # (then v1 or another configuration is their choice), or it had produced recommendations
    # (then the rollback handed over to v1). Either way the seed did not make the current
    # activation and leaves it alone; an operator re-activates v2 in the admin (Z-1).
    if ScoringConfig.objects.filter(version="v2-deterministic").exists():
        return
    # v2 replaces only an earlier seed. A configuration an operator activated stays active, and
    # v2 is stored inactive (recommendation-evaluation, "Replacing the active configuration").
    operator_choice = (
        ScoringConfig.objects.filter(is_active=True)
        .exclude(version="v1-deterministic")
        .exists()
    )
    if not operator_choice:
        # One active configuration at a time: deactivate first, then activate v2.
        ScoringConfig.objects.filter(is_active=True).update(is_active=False)
    ScoringConfig.objects.create(
        version="v2-deterministic",
        description=DESCRIPTION,
        weights=WEIGHTS,
        params=PARAMS,
        is_active=not operator_choice,
    )


def unseed(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    ScoringConfig = apps.get_model("recommendations", "ScoringConfig")
    v2 = ScoringConfig.objects.filter(version="v2-deterministic").first()
    if v2 is None or not v2.is_active:
        return
    ScoringConfig.objects.filter(pk=v2.pk).update(is_active=False)
    ScoringConfig.objects.filter(version="v1-deterministic").update(is_active=True)
    ScoringConfig.objects.filter(pk=v2.pk, recommendations__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("recommendations", "0002_seed_v1_deterministic")]

    operations = [migrations.RunPython(seed, unseed)]
