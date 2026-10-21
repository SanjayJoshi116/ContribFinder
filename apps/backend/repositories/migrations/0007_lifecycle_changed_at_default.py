from typing import Any

import django.utils.timezone
from django.db import migrations, models
from django.db.models import F


def backfill_lifecycle_changed_at(apps: Any, schema_editor: Any) -> None:
    """The closest real time a row without a transition time has: its metadata fetch."""
    Repository = apps.get_model("repositories", "Repository")
    Repository.objects.filter(lifecycle_changed_at__isnull=True).update(
        lifecycle_changed_at=F("synced_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("repositories", "0006_refresh_failed_at"),
    ]

    operations = [
        migrations.RunPython(backfill_lifecycle_changed_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="repository",
            name="lifecycle_changed_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="repository",
            name="refresh_queued_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
