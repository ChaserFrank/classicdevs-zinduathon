from django.contrib import admin

from . import models as m


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class SubScoreInline(ReadOnlyInline):
    model = m.SubScore
    fields = ("key", "value", "reason")


class AnalysisSkillInline(ReadOnlyInline):
    model = m.AnalysisSkill
    fields = ("skill", "label", "evidence")


class FlagInline(ReadOnlyInline):
    model = m.Flag
    fields = ("type", "reason")


@admin.register(m.Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    """Analyses are produced by the pipeline; the admin is for reading them."""

    list_display = (
        "github_login",
        "status",
        "signal_score",
        "summary_source",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "summary_source")
    search_fields = ("github_login", "public_id")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in m.Analysis._meta.fields]
    inlines = (SubScoreInline, AnalysisSkillInline, FlagInline)

    def has_add_permission(self, request):
        return False


@admin.register(m.Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ("owner_login", "name", "is_fork", "pushed_at")
    search_fields = ("owner_login", "name")
    list_filter = ("is_fork",)


@admin.register(m.ClaimedSkill)
class ClaimedSkillAdmin(admin.ModelAdmin):
    list_display = ("raw_text", "skill", "job_seeker", "position")
    search_fields = ("raw_text", "job_seeker__user__email")


@admin.register(m.GithubCache)
class GithubCacheAdmin(admin.ModelAdmin):
    list_display = ("url", "etag", "fetched_at")
    search_fields = ("url",)
    exclude = ("payload",)
