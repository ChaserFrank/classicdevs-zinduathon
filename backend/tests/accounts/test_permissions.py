"""Role permission classes, exercised through a throwaway view per class."""

import pytest
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    IsAdminRole,
    IsApprovedRecruiter,
    IsApprovedRecruiterOrAdmin,
    IsJobSeeker,
    IsOwnerOrAdmin,
)
from tests.factories import RecruiterFactory

pytestmark = pytest.mark.django_db


def make_view(permission):
    class View(APIView):
        permission_classes = (permission,)

        def get(self, request):
            return Response({"ok": True})

    return View.as_view()


class Thing:
    def __init__(self, user):
        self.user = user


class OwnedView(APIView):
    permission_classes = (IsOwnerOrAdmin,)
    owner = None

    def get(self, request):
        self.check_object_permissions(request, Thing(OwnedView.owner))
        return Response({"ok": True})


urlpatterns = [
    path("job-seeker", make_view(IsJobSeeker)),
    path("recruiter", make_view(IsApprovedRecruiter)),
    path("recruiter-or-admin", make_view(IsApprovedRecruiterOrAdmin)),
    path("admin", make_view(IsAdminRole)),
    path("owned", OwnedView.as_view()),
]


@pytest.fixture(autouse=True)
def _urls(settings):
    settings.ROOT_URLCONF = __name__


@pytest.mark.parametrize(
    ("url", "who", "expected"),
    [
        ("/job-seeker", "job_seeker", 200),
        ("/job-seeker", "recruiter", 403),
        ("/job-seeker", "admin_user", 403),
        ("/recruiter", "recruiter", 200),
        ("/recruiter", "job_seeker", 403),
        ("/recruiter", "admin_user", 403),
        ("/recruiter-or-admin", "recruiter", 200),
        ("/recruiter-or-admin", "admin_user", 200),
        ("/recruiter-or-admin", "job_seeker", 403),
        ("/admin", "admin_user", 200),
        ("/admin", "recruiter", 403),
        ("/admin", "job_seeker", 403),
    ],
)
def test_role_matrix(request, auth_client, url, who, expected):
    user = request.getfixturevalue(who)
    assert auth_client(user).get(url).status_code == expected


@pytest.mark.parametrize("status", ["pending", "rejected", "suspended"])
@pytest.mark.parametrize("url", ["/recruiter", "/recruiter-or-admin"])
def test_unapproved_recruiters_get_specific_code(auth_client, status, url):
    user = RecruiterFactory(profile__approval_status=status)
    response = auth_client(user).get(url)
    assert response.status_code == 403
    assert response.json()["code"] == "recruiter_not_approved"


def test_generic_denial_code(auth_client, job_seeker):
    assert auth_client(job_seeker).get("/admin").json()["code"] == "permission_denied"


def test_anonymous_gets_401(api_client):
    assert api_client.get("/job-seeker").status_code == 401


def test_owner_or_admin(auth_client, job_seeker, recruiter, admin_user):
    OwnedView.owner = job_seeker
    assert auth_client(job_seeker).get("/owned").status_code == 200
    assert auth_client(admin_user).get("/owned").status_code == 200
    assert auth_client(recruiter).get("/owned").status_code == 403
