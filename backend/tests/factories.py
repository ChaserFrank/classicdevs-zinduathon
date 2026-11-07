"""factory_boy factories. One per model; later phases add theirs here."""

import factory
from django.utils import timezone

from apps.accounts.models import GithubAccount, JobSeekerProfile, Role, User
from apps.companies.models import ApprovalStatus, Company, RecruiterProfile

PASSWORD = "correct-horse-battery"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    role = Role.JOB_SEEKER
    email_verified_at = factory.LazyFunction(timezone.now)
    password = factory.PostGenerationMethodCall("set_password", PASSWORD)

    @factory.post_generation
    def _save(obj, create, extracted, **kwargs):
        if create:
            obj.save()


class JobSeekerProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JobSeekerProfile

    user = factory.SubFactory(UserFactory, role=Role.JOB_SEEKER)
    headline = "Developer"
    location = "Nairobi"


class JobSeekerFactory(UserFactory):
    """A job seeker user with their profile."""

    role = Role.JOB_SEEKER
    profile = factory.RelatedFactory(JobSeekerProfileFactory, factory_related_name="user")


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    name = factory.Sequence(lambda n: f"Company {n}")


class RecruiterProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RecruiterProfile

    user = factory.SubFactory(UserFactory, role=Role.RECRUITER)
    company = factory.SubFactory(CompanyFactory)
    job_title = "Talent lead"
    approval_status = ApprovalStatus.APPROVED


class RecruiterFactory(UserFactory):
    """An approved recruiter. Pass `profile__approval_status=...` for other states."""

    role = Role.RECRUITER
    profile = factory.RelatedFactory(RecruiterProfileFactory, factory_related_name="user")


class AdminFactory(UserFactory):
    role = Role.ADMIN
    is_staff = True
    is_superuser = True


class GithubAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GithubAccount

    user = factory.SubFactory(JobSeekerFactory)
    github_id = factory.Sequence(lambda n: 1000 + n)
    login = factory.Sequence(lambda n: f"dev{n}")
    avatar_url = "https://avatars.githubusercontent.com/u/1"
