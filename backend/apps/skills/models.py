"""The skill catalogue. Detection rules read these tables, so admins can teach SkillProof a new
framework (add a DependencyMapping row) without a code change or deploy."""

from django.db import models

from apps.core.models import TimeStampedModel


class Category(models.TextChoices):
    LANGUAGE = "language", "Language"
    FRAMEWORK = "framework", "Framework"
    PRACTICE = "practice", "Practice"
    TOOL = "tool", "Tool"


class Skill(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    category = models.CharField(max_length=16, choices=Category.choices)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(category__in=Category.values), name="skills_skill_category_valid"
            )
        ]

    def __str__(self) -> str:
        return self.name


class SkillAlias(TimeStampedModel):
    """Other names for a skill: "js" → JavaScript, GitHub's "Jupyter Notebook" → Python. Used to
    read GitHub language names and to match what people type as claimed skills."""

    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="aliases")
    alias = models.CharField(max_length=80, unique=True, help_text="Lowercase")

    class Meta:
        verbose_name_plural = "skill aliases"
        ordering = ("alias",)

    def __str__(self) -> str:
        return f"{self.alias} → {self.skill}"

    def save(self, *args, **kwargs):
        self.alias = self.alias.strip().lower()
        super().save(*args, **kwargs)


class Ecosystem(models.TextChoices):
    NPM = "npm", "npm"
    PYPI = "pypi", "PyPI"
    GO = "go", "Go modules"
    MAVEN = "maven", "Maven"


class DependencyMapping(TimeStampedModel):
    """A package in a manifest that proves a skill: npm `react` → React."""

    ecosystem = models.CharField(max_length=8, choices=Ecosystem.choices)
    package_name = models.CharField(max_length=214, help_text="Normalised lowercase name")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="dependency_mappings")

    class Meta:
        ordering = ("ecosystem", "package_name")
        constraints = [
            models.UniqueConstraint(
                fields=("ecosystem", "package_name"), name="skills_depmap_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(ecosystem__in=Ecosystem.values),
                name="skills_depmap_ecosystem_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ecosystem}:{self.package_name} → {self.skill}"

    def save(self, *args, **kwargs):
        from apps.analysis.services.manifests import normalise_package

        self.package_name = normalise_package(self.ecosystem, self.package_name)
        super().save(*args, **kwargs)
