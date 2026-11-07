"""Seed the skill catalogue from apps/skills/catalogue.py (brief section 8.2).

Idempotent (get_or_create), so it is safe on databases where an admin already added rows.
"""

from django.db import migrations
from django.utils.text import slugify


def seed(apps, schema_editor):
    from apps.analysis.services.manifests import normalise_package
    from apps.skills.catalogue import SEED

    Skill = apps.get_model("skills", "Skill")
    SkillAlias = apps.get_model("skills", "SkillAlias")
    DependencyMapping = apps.get_model("skills", "DependencyMapping")
    for name, (category, aliases, deps) in SEED.items():
        slug = slugify(name.replace("+", "plus").replace("#", "sharp").replace(".", "-")) or name
        skill, _ = Skill.objects.get_or_create(
            name=name, defaults={"slug": slug, "category": category}
        )
        for alias in aliases:
            SkillAlias.objects.get_or_create(alias=alias.lower(), defaults={"skill": skill})
        for ecosystem, packages in deps.items():
            for package in packages:
                DependencyMapping.objects.get_or_create(
                    ecosystem=ecosystem,
                    package_name=normalise_package(ecosystem, package),
                    defaults={"skill": skill},
                )


class Migration(migrations.Migration):
    dependencies = [("skills", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
