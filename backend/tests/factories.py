"""factory_boy factories. One per model; later phases add theirs here."""

import factory

from apps.accounts.models import Role, User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    role = Role.JOB_SEEKER
    password = factory.PostGenerationMethodCall("set_password", "correct-horse-battery")

    @factory.post_generation
    def _save(obj, create, extracted, **kwargs):
        if create:
            obj.save()
