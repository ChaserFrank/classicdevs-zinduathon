from rest_framework import serializers


class ErrorSerializer(serializers.Serializer):
    """The error shape every endpoint returns (documented once, referenced everywhere)."""

    code = serializers.CharField(help_text="Stable machine-readable code, e.g. `not_found`.")
    message = serializers.CharField(help_text="Human-readable sentence safe to show users.")
    fields = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        required=False,
        help_text="Validation errors per field (only when code is `validation_error`).",
    )


class HealthChecksSerializer(serializers.Serializer):
    database = serializers.ChoiceField(choices=["ok", "down"])
    redis = serializers.ChoiceField(choices=["ok", "down"])


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    checks = HealthChecksSerializer()
    version = serializers.CharField()
    commit_sha = serializers.CharField(allow_blank=True)
    time = serializers.DateTimeField()
