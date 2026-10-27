from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F


def repair(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Raise every rank of a developer who has a rank 0 by one: order kept, nothing deleted."""
    Recommendation = apps.get_model("recommendations", "Recommendation")
    affected = Recommendation.objects.filter(rank=0).values("developer_id")
    Recommendation.objects.filter(developer_id__in=affected).update(rank=F("rank") + 1)


class Migration(migrations.Migration):
    dependencies = [("recommendations", "0004_issue_snapshots_and_reason_types")]

    operations = [
        migrations.RunPython(repair, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="recommendation",
            constraint=models.CheckConstraint(
                condition=models.Q(rank__gte=1), name="recommendation_rank_positive"
            ),
        ),
    ]
