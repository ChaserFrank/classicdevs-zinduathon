from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import phone as phone_utils
from apps.accounts.models import ConsentRecord, ConsentType, User
from apps.core import audit
from apps.core.schema import errors

from . import services, webhooks
from .models import Channel, Delivery, DeliveryStatus, Notification, NotificationPreference
from .serializers import (
    NotificationSerializer,
    PreferenceMatrixSerializer,
    PreferenceUpdateSerializer,
    ReadAllSerializer,
    WebhookAckSerializer,
)


def _sms_ready(user) -> bool:
    return user.is_phone_verified and services._consents(user).get(ConsentType.SMS_FEEDBACK, False)


class PreferencesView(APIView):
    permission_classes = (IsAuthenticated,)

    def _response(self, user):
        return Response({"matrix": services.matrix(user), "sms_ready": _sms_ready(user)})

    @extend_schema(
        tags=["Notifications"],
        summary="My notification preferences",
        description=(
            "Matrix of notification kind × channel for your role. SMS is only sent when "
            "`smsReady` is true (verified phone and SMS consent)."
        ),
        responses={200: PreferenceMatrixSerializer, **errors((401, "not_authenticated"))},
        examples=[
            OpenApiExample(
                "Job seeker",
                value={
                    "matrix": {
                        "analysisCompleted": {"inApp": True, "email": True, "sms": False},
                        "recruiterFeedback": {"inApp": True, "email": True, "sms": True},
                    },
                    "smsReady": True,
                },
                response_only=True,
            )
        ],
    )
    def get(self, request):
        return self._response(request.user)

    @extend_schema(
        tags=["Notifications"],
        summary="Change notification preferences",
        description=(
            "Send only the cells you change. Turning SMS or email on for feedback also records "
            "the matching consent (Kenya DPA); turning every SMS kind off withdraws SMS consent."
        ),
        request=PreferenceUpdateSerializer,
        responses={200: PreferenceMatrixSerializer, **errors((400, "validation_error"))},
        examples=[
            OpenApiExample(
                "Feedback by SMS",
                value={
                    "preferences": [
                        {"kind": "recruiter_feedback", "channel": "sms", "enabled": True}
                    ]
                },
                request_only=True,
            )
        ],
    )
    @transaction.atomic
    def put(self, request):
        serializer = PreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        allowed = services.KINDS_BY_ROLE.get(user.role, ())
        bad = [
            f"{c['kind']}/{c['channel']}"
            for c in serializer.validated_data["preferences"]
            if c["kind"] not in allowed or c["channel"] not in services.CHANNELS[c["kind"]]
        ]
        if bad:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"preferences": [f"Not available: {', '.join(bad)}"]})
        services.ensure_defaults(user)
        for change in serializer.validated_data["preferences"]:
            NotificationPreference.objects.update_or_create(
                user=user,
                kind=change["kind"],
                channel=change["channel"],
                defaults={"enabled": change["enabled"]},
            )
        _sync_consents(user, request)
        return self._response(user)


def _sync_consents(user, request) -> None:
    """Keep consent records truthful when preferences change (append-only history)."""
    from apps.accounts.services import record_consents

    current = services._consents(user)
    prefs = {(p.kind, p.channel): p.enabled for p in user.notification_preferences.all()}
    wants = {
        "email_feedback": any(
            v
            for (k, c), v in prefs.items()
            if c == Channel.EMAIL and k not in services.TRANSACTIONAL_EMAIL
        ),
        "sms_feedback": any(v for (k, c), v in prefs.items() if c == Channel.SMS),
    }
    changed = {name: value for name, value in wants.items() if current.get(name, False) != value}
    if changed:
        record_consents(user, changed, request)


class NotificationListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    filter_backends = ()

    @extend_schema(
        tags=["Notifications"],
        summary="My inbox",
        parameters=[OpenApiParameter("unread", bool, description="Only unread notifications")],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user).order_by("-created_at")
        if str(self.request.query_params.get("unread", "")).lower() in {"1", "true"}:
            queryset = queryset.filter(read_at__isnull=True)
        return queryset


class NotificationReadView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Notifications"],
        summary="Mark a notification read",
        request=None,
        responses={200: NotificationSerializer, **errors((404, "not_found"))},
    )
    def post(self, request, public_id):
        notification = Notification.objects.filter(public_id=public_id, user=request.user).first()
        if notification is None:
            raise NotFound()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Notifications"],
        summary="Mark all notifications read",
        request=None,
        responses={200: ReadAllSerializer},
    )
    def post(self, request):
        updated = Notification.objects.filter(user=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response({"updated": updated})


class _WebhookView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()  # provider traffic; authenticity comes from the signature

    def check_signature(self, request) -> bytes:
        raw = request.body
        if not webhooks.verify_signature(raw, request.headers):
            raise PermissionDenied("Invalid webhook signature.")
        return raw


class DeliveryReportView(_WebhookView):
    @extend_schema(
        tags=["Notifications"],
        summary="Thrivewave delivery report (webhook)",
        description=(
            "Called by Thrivewave. Verified by `X-Thrivewave-Signature` (HMAC-SHA256 of the body "
            "with THRIVEWAVE_WEBHOOK_SECRET) or `X-Thrivewave-Secret`. Idempotent; answers 200 "
            "quickly even for unknown message ids."
        ),
        request={"application/json": {"type": "object"}},
        responses={200: WebhookAckSerializer, **errors((403, "permission_denied"))},
        auth=[],
    )
    def post(self, request):
        raw = self.check_signature(request)
        message_id, outcome = webhooks.parse_delivery_report(raw)
        if not message_id or outcome is None:
            return Response({"ok": True, "updated": False})
        delivery = Delivery.objects.filter(
            provider="thrivewave", provider_message_id=message_id
        ).first()
        if delivery is None or delivery.status in (DeliveryStatus.DELIVERED, outcome):
            return Response({"ok": True, "updated": False})
        delivery.status = outcome
        if outcome == DeliveryStatus.DELIVERED:
            delivery.delivered_at = timezone.now()
        else:
            delivery.last_error = "Provider reported delivery failure"
        delivery.save(update_fields=["status", "delivered_at", "last_error", "updated_at"])
        return Response({"ok": True, "updated": True})


STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}


class InboundSmsView(_WebhookView):
    @extend_schema(
        tags=["Notifications"],
        summary="Thrivewave inbound SMS (webhook)",
        description=(
            "Replies of STOP (or UNSUBSCRIBE, END…) turn off every SMS preference for the "
            "sender's number and record SMS consent as withdrawn. Other messages are ignored."
        ),
        request={"application/json": {"type": "object"}},
        responses={200: WebhookAckSerializer, **errors((403, "permission_denied"))},
        auth=[],
    )
    def post(self, request):
        raw = self.check_signature(request)
        sender, text = webhooks.parse_inbound(raw)
        if text.strip().lower() not in STOP_WORDS:
            return Response({"ok": True, "updated": False})
        try:
            e164 = phone_utils.normalise(sender)
        except phone_utils.InvalidPhone:
            return Response({"ok": True, "updated": False})
        user = User.objects.filter(phone=e164).first()
        if user is None:
            return Response({"ok": True, "updated": False})
        with transaction.atomic():
            services.ensure_defaults(user)
            user.notification_preferences.filter(channel=Channel.SMS).update(enabled=False)
            ConsentRecord.objects.create(
                user=user,
                consent_type=ConsentType.SMS_FEEDBACK,
                granted=False,
                policy_version=settings.POLICY_VERSION,
            )
            audit.record("notifications.sms_opt_out", target=user, metadata={"via": "sms_stop"})
        return Response({"ok": True, "updated": True})
