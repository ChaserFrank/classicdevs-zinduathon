from django.contrib import admin, messages

from apps.accounts.errors import EmailNotVerified

from . import services
from .models import ApprovalStatus, Company, RecruiterProfile


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "website", "location", "is_verified", "created_at")
    list_filter = ("is_verified",)
    search_fields = ("name",)
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "job_title", "approval_status", "reviewed_by", "reviewed_at")
    list_filter = ("approval_status", "company")
    search_fields = ("user__email", "user__full_name", "company__name")
    autocomplete_fields = ("company",)
    # Status changes go through the actions so they are audited; not editable inline.
    readonly_fields = (
        "approval_status",
        "reviewed_by",
        "reviewed_at",
        "review_note",
        "created_at",
        "updated_at",
    )
    actions = ("approve_selected", "reject_selected", "suspend_selected")

    def _apply(self, request, queryset, status):
        done, skipped = 0, 0
        for profile in queryset.select_related("user"):
            try:
                services.set_status(profile, status, reviewer=request.user, request=request)
                done += 1
            except EmailNotVerified:
                skipped += 1
        self.message_user(request, f"{done} recruiter(s) set to {status}.", messages.SUCCESS)
        if skipped:
            self.message_user(
                request, f"{skipped} skipped: email not verified yet.", messages.WARNING
            )

    @admin.action(description="Approve selected recruiters")
    def approve_selected(self, request, queryset):
        self._apply(request, queryset, ApprovalStatus.APPROVED)

    @admin.action(description="Reject selected recruiters")
    def reject_selected(self, request, queryset):
        self._apply(request, queryset, ApprovalStatus.REJECTED)

    @admin.action(description="Suspend selected recruiters")
    def suspend_selected(self, request, queryset):
        self._apply(request, queryset, ApprovalStatus.SUSPENDED)
