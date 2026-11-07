from django.contrib import admin, messages

from .models import Feedback, JobPosting, JobRequiredSkill, Moderation, ProfileView, ShortlistEntry
from .services import feedback as feedback_service


class JobRequiredSkillInline(admin.TabularInline):
    model = JobRequiredSkill
    extra = 1
    autocomplete_fields = ("skill",)


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "status", "employment_type", "remote_policy", "created_at")
    list_filter = ("status", "employment_type", "remote_policy")
    search_fields = ("title", "company__name")
    readonly_fields = ("public_id", "created_at", "updated_at")
    inlines = (JobRequiredSkillInline,)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    """Held messages wait here for review: release sends them, reject keeps them unsent."""

    list_display = (
        "created_at",
        "company_name",
        "recruiter",
        "job_seeker",
        "status",
        "moderation",
        "held_reason",
    )
    list_filter = ("moderation", "status")
    search_fields = ("message", "company_name", "recruiter__email", "job_seeker__user__email")
    readonly_fields = [f.name for f in Feedback._meta.fields]
    actions = ("release_selected", "reject_selected")

    def has_add_permission(self, request):
        return False

    @admin.action(description="Release held feedback (send it)")
    def release_selected(self, request, queryset):
        held = list(queryset.filter(moderation=Moderation.HELD))
        for feedback in held:
            feedback_service.release(feedback, admin=request.user, request=request)
        self.message_user(request, f"{len(held)} message(s) released.", messages.SUCCESS)

    @admin.action(description="Reject held feedback (never send)")
    def reject_selected(self, request, queryset):
        held = list(queryset.filter(moderation=Moderation.HELD))
        for feedback in held:
            feedback_service.reject(feedback, admin=request.user, request=request)
        self.message_user(request, f"{len(held)} message(s) rejected.", messages.SUCCESS)


@admin.register(ShortlistEntry)
class ShortlistEntryAdmin(admin.ModelAdmin):
    list_display = ("recruiter", "job_seeker", "job_posting", "stage", "updated_at")
    list_filter = ("stage",)
    search_fields = ("recruiter__email", "job_seeker__user__email")


@admin.register(ProfileView)
class ProfileViewAdmin(admin.ModelAdmin):
    list_display = ("viewed_at", "recruiter", "job_seeker")
    search_fields = ("recruiter__email", "job_seeker__user__email")
