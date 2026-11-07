from django.contrib import admin, messages

from .models import Delivery, DeliveryStatus, Notification, NotificationPreference


class DeliveryInline(admin.TabularInline):
    model = Delivery
    extra = 0
    can_delete = False
    fields = ("channel", "recipient", "status", "attempts", "last_error", "sent_at", "delivered_at")
    readonly_fields = fields


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "kind", "title", "read_at")
    list_filter = ("kind",)
    search_fields = ("user__email", "title")
    readonly_fields = ("public_id", "created_at", "updated_at")
    inlines = (DeliveryInline,)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "channel", "enabled")
    list_filter = ("kind", "channel", "enabled")
    search_fields = ("user__email",)


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "channel",
        "provider",
        "recipient",
        "status",
        "attempts",
        "last_error",
    )
    list_filter = ("status", "channel", "provider")
    search_fields = ("recipient", "provider_message_id", "notification__user__email")
    readonly_fields = [f.name for f in Delivery._meta.fields]
    actions = ("retry_selected",)

    @admin.action(description="Retry selected failed deliveries")
    def retry_selected(self, request, queryset):
        from .tasks import deliver

        failed = list(queryset.filter(status=DeliveryStatus.FAILED))
        for delivery in failed:
            Delivery.objects.filter(pk=delivery.pk).update(status=DeliveryStatus.QUEUED, attempts=0)
            deliver.delay(delivery.pk)
        self.message_user(request, f"{len(failed)} delivery(ies) queued again.", messages.SUCCESS)
