import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.tokens import issue_tokens
from tests.factories import AdminFactory, JobSeekerFactory, RecruiterFactory, UserFactory


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the cache; start every test with a clean slate."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def job_seeker(db):
    return JobSeekerFactory()


@pytest.fixture
def recruiter(db):
    return RecruiterFactory()


@pytest.fixture
def pending_recruiter(db):
    return RecruiterFactory(profile__approval_status="pending")


@pytest.fixture
def admin_user(db):
    return AdminFactory()


@pytest.fixture
def auth_client():
    """auth_client(user) → an APIClient sending that user's access token."""

    def make(user) -> APIClient:
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
        return client

    return make
