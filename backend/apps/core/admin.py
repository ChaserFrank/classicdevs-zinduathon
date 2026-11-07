from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: the audit log must not be editable, even by admins."""

    list_display = ("created_at", "action", "actor", "target_type", "target_id", "ip_address")
    list_filter = ("action", "target_type")
    search_fields = ("action", "target_id", "actor__email")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
