from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


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
