from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from services.job_guard import is_stalled
from services.jobs import STEPS_BY_JOB_TYPE

from .models import SyncJob


class SyncJobSerializer(serializers.ModelSerializer[SyncJob]):
    """Public view of a job. ``metadata`` and ``error_detail`` stay internal. ``stalled``: RUNNING
    with no heartbeat for ``SYNC_STALE_AFTER_SECONDS`` (its worker died); reading changes
    nothing, recovery still resumes it."""

    steps = serializers.DictField(child=serializers.ChoiceField(choices=SyncJob.StepState.choices))
    stalled = serializers.SerializerMethodField()

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
            "stalled",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_stalled(self, instance: SyncJob) -> bool:
        return is_stalled(instance, timezone.now())

    def to_representation(self, instance: SyncJob) -> dict[str, Any]:
        data = super().to_representation(instance)
        # Jobs created before a step existed report it as pending, in step order.
        order = STEPS_BY_JOB_TYPE.get(instance.job_type, ())
        data["steps"] = {**dict.fromkeys(order, SyncJob.StepState.PENDING.value), **data["steps"]}
        return data


class SyncStatusSerializer(serializers.Serializer[dict[str, object]]):
    job = SyncJobSerializer(allow_null=True)
    last_synced_at = serializers.DateTimeField(allow_null=True)


class DataVersionsSerializer(serializers.Serializer[object]):
    """When each derived data area last changed; null when the area holds no data."""

    github = serializers.DateTimeField(allow_null=True)
    profile = serializers.DateTimeField(allow_null=True)
    recommendations = serializers.DateTimeField(allow_null=True)
