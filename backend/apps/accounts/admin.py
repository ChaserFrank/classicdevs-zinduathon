from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ConsentRecord, GithubAccount, JobSeekerProfile, User, VerificationCode


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("email", "full_name", "role", "is_active", "email_verified_at", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "full_name", "phone")
    readonly_fields = ("public_id", "last_login", "date_joined", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("public_id", "email", "password")}),
        ("Profile", {"fields": ("full_name", "role", "phone")}),
        ("Verification", {"fields": ("email_verified_at", "phone_verified_at")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        ("Dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "role", "password1", "password2")}),
    )


@admin.register(JobSeekerProfile)
class JobSeekerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "headline", "location", "card_visible", "open_to_work")
    list_filter = ("card_visible", "open_to_work")
    search_fields = ("user__email", "user__full_name", "headline")
    readonly_fields = ("created_at", "updated_at")


@admin.register(GithubAccount)
class GithubAccountAdmin(admin.ModelAdmin):
    list_display = ("login", "user", "github_id", "connected_at", "last_synced_at")
    search_fields = ("login", "user__email")
    # The encrypted token is never shown or edited here.
    exclude = ("access_token_encrypted",)
    readonly_fields = ("github_id", "token_scopes", "connected_at", "last_synced_at", "created_at")


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "consent_type", "granted", "policy_version", "ip_address")
    list_filter = ("consent_type", "granted", "policy_version")
    search_fields = ("user__email",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "created_at", "expires_at", "used_at", "attempts")
    list_filter = ("purpose",)
    search_fields = ("user__email",)
    exclude = ("code_hash",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
