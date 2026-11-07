from django.contrib import admin

from .models import DependencyMapping, Skill, SkillAlias


class SkillAliasInline(admin.TabularInline):
    model = SkillAlias
    extra = 1


class DependencyMappingInline(admin.TabularInline):
    model = DependencyMapping
    extra = 1


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "slug")
    list_filter = ("category",)
    search_fields = ("name", "aliases__alias")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (SkillAliasInline, DependencyMappingInline)


@admin.register(DependencyMapping)
class DependencyMappingAdmin(admin.ModelAdmin):
    list_display = ("ecosystem", "package_name", "skill")
    list_filter = ("ecosystem",)
    search_fields = ("package_name", "skill__name")
    autocomplete_fields = ("skill",)


@admin.register(SkillAlias)
class SkillAliasAdmin(admin.ModelAdmin):
    list_display = ("alias", "skill")
    search_fields = ("alias", "skill__name")
    autocomplete_fields = ("skill",)
