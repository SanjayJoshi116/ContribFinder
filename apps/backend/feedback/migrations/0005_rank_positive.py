from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def repair(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """A rank 0 snapshot becomes null, which the feedback report already reads it as."""
    RecommendationFeedback = apps.get_model("feedback", "RecommendationFeedback")
    RecommendationFeedback.objects.filter(rank=0).update(rank=None)


class Migration(migrations.Migration):
    dependencies = [("feedback", "0004_dismiss_reasons")]

    operations = [
        migrations.RunPython(repair, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="recommendationfeedback",
            constraint=models.CheckConstraint(
                condition=models.Q(rank__isnull=True) | models.Q(rank__gte=1),
                name="feedback_rank_positive",
            ),
        ),
    ]
