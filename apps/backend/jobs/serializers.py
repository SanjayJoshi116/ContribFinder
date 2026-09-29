from rest_framework import serializers

from .models import SyncJob


class SyncJobSerializer(serializers.ModelSerializer[SyncJob]):
    """Public view of a job. ``metadata`` and ``error_detail`` stay internal."""

    steps = serializers.DictField(child=serializers.ChoiceField(choices=SyncJob.StepState.choices))

    class Meta:
        model = SyncJob
        fields = [
            "id",
            "job_type",
            "status",
            "steps",
            "attempts",
            "error_code",
            "created_at",
            "started_at",
            "completed_at",
        ]
        read_only_fields = fields


class SyncStatusSerializer(serializers.Serializer[dict[str, object]]):
    job = SyncJobSerializer(allow_null=True)
    last_synced_at = serializers.DateTimeField(allow_null=True)
