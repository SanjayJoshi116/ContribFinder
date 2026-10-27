from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F


def repair(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Raise every matched-issue rank of a recommendation that has a rank 0 by one."""
    RecommendedIssue = apps.get_model("issues", "RecommendedIssue")
    affected = RecommendedIssue.objects.filter(rank=0).values("recommendation_id")
    RecommendedIssue.objects.filter(recommendation_id__in=affected).update(rank=F("rank") + 1)


class Migration(migrations.Migration):
    dependencies = [("issues", "0001_initial")]

    operations = [
        migrations.RunPython(repair, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="recommendedissue",
            constraint=models.CheckConstraint(
                condition=models.Q(rank__gte=1), name="recommended_issue_rank_positive"
            ),
        ),
    ]
