from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer[dict[str, object]]):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField(required=False)


class ErrorSerializer(serializers.Serializer[dict[str, object]]):
    """Standard error envelope, referenced by every endpoint's error responses."""

    error = ErrorDetailSerializer()


class HealthSerializer(serializers.Serializer[dict[str, object]]):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    checks = serializers.DictField(
        child=serializers.ChoiceField(choices=["ok", "unavailable", "not_configured"])
    )


def error_responses(*statuses: int) -> dict[int, type[ErrorSerializer]]:
    """OpenAPI response map documenting the standard error envelope for given statuses."""
    return dict.fromkeys(statuses, ErrorSerializer)
