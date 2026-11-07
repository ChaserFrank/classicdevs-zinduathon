import pytest
from django.db import IntegrityError, connection

from apps.accounts.models import Role, User

pytestmark = pytest.mark.django_db


def test_create_user_lowercases_email_and_hashes_password():
    user = User.objects.create_user("Ann.Wanjiru@Example.COM", "s3cret-pass!")
    assert user.email == "ann.wanjiru@example.com"
    assert user.check_password("s3cret-pass!")
    assert user.role == Role.JOB_SEEKER
    assert not user.is_staff
    assert not user.is_email_verified
    assert not user.is_phone_verified


def test_user_without_password_cannot_sign_in_with_password():
    user = User.objects.create_user("gh@example.com")
    assert not user.has_usable_password()


def test_email_is_required():
    with pytest.raises(ValueError):
        User.objects.create_user("")


def test_email_unique_case_insensitive():
    User.objects.create_user("ann@example.com", "x")
    with pytest.raises(IntegrityError):
        User.objects.create_user("ANN@example.com", "x")


def test_db_constraint_blocks_case_variant_written_by_raw_sql():
    User.objects.create_user("ann@example.com", "x")
    with pytest.raises(IntegrityError), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO accounts_user (public_id, email, role, full_name, password, is_active,"
            " is_staff, is_superuser, date_joined, created_at, updated_at)"
            " VALUES (gen_random_uuid(), 'Ann@Example.com', 'job_seeker', '', '', true, false,"
            " false, now(), now(), now())"
        )


def test_lookup_by_email_is_case_insensitive():
    User.objects.create_user("ann@example.com", "x")
    assert User.objects.get_by_natural_key("ANN@EXAMPLE.COM").email == "ann@example.com"


def test_phone_unique_when_set_but_many_nulls_allowed():
    User.objects.create_user("a@example.com", "x", phone="+254712345678")
    User.objects.create_user("b@example.com", "x")
    User.objects.create_user("c@example.com", "x", phone="")  # blank → NULL
    with pytest.raises(IntegrityError):
        User.objects.create_user("d@example.com", "x", phone="+254712345678")


def test_role_check_constraint():
    with pytest.raises(IntegrityError):
        User.objects.create_user("x@example.com", "x", role="superhero")


def test_create_superuser_is_admin_role():
    admin = User.objects.create_superuser("Admin@Example.com", "x")
    assert admin.role == Role.ADMIN
    assert admin.is_staff and admin.is_superuser
    assert str(admin) == "admin@example.com"


def test_create_superuser_rejects_non_admin_role():
    with pytest.raises(ValueError):
        User.objects.create_superuser("a@example.com", "x", role=Role.RECRUITER)
