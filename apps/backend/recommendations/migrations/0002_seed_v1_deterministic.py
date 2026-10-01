from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

# Frozen copy of services/ranking/config.py V1_*: a migration must not change when that
# module does later.
WEIGHTS = {
    "skill": 0.40,
    "language": 0.20,
    "interest": 0.15,
    "framework": 0.10,
    "activity": 0.10,
    "openness": 0.05,
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
}
DESCRIPTION = (
    "Initial deterministic weights (SRS-2 §30). Experimental starting values, not product truth; "
    "change them only through a new version evaluated against benchmarks."
)


def seed(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    ScoringConfig = apps.get_model("recommendations", "ScoringConfig")
    ScoringConfig.objects.update_or_create(
        version="v1-deterministic",
        defaults={
            "description": DESCRIPTION,
            "weights": WEIGHTS,
            "params": PARAMS,
            "is_active": not ScoringConfig.objects.filter(is_active=True).exists(),
        },
    )


def unseed(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    apps.get_model("recommendations", "ScoringConfig").objects.filter(
        version="v1-deterministic", recommendations__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("recommendations", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
