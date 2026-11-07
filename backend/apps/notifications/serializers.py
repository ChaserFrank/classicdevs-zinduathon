from rest_framework import serializers

from .models import Channel, Kind, Notification


class NotificationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = Notification
        fields = ("id", "kind", "title", "body", "link_path", "read_at", "created_at")


class PreferenceMatrixSerializer(serializers.Serializer):
    matrix = serializers.DictField(
        child=serializers.DictField(child=serializers.BooleanField()),
        help_text="kind → channel → enabled. Only kinds for your role and channels that exist.",
    )
    sms_ready = serializers.BooleanField(help_text="Phone verified and SMS consent given.")


class PreferenceChangeSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Kind.values)
    channel = serializers.ChoiceField(choices=Channel.values)
    enabled = serializers.BooleanField()


class PreferenceUpdateSerializer(serializers.Serializer):
    preferences = PreferenceChangeSerializer(many=True)


class ReadAllSerializer(serializers.Serializer):
    updated = serializers.IntegerField()


class WebhookAckSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    updated = serializers.BooleanField(required=False)
