import pytest

from tests.factories import UserFactory

pytestmark = pytest.mark.django_db
URL = "/api/v1/me"


def test_requires_sign_in(api_client):
    assert api_client.get(URL).status_code == 401


def test_job_seeker_me(auth_client, job_seeker):
    body = auth_client(job_seeker).get(URL).json()
    assert set(body) == {
        "id",
        "email",
        "role",
        "fullName",
        "phone",
        "emailVerified",
        "phoneVerified",
        "hasPassword",
        "dateJoined",
        "github",
        "jobSeekerProfile",
        "recruiterProfile",
    }
    assert body["id"] == str(job_seeker.public_id)
    assert body["github"] is None


def test_recruiter_me_shows_status_and_company(auth_client, pending_recruiter):
    body = auth_client(pending_recruiter).get(URL).json()
    assert body["jobSeekerProfile"] is None
    assert body["recruiterProfile"]["approvalStatus"] == "pending"
    assert set(body["recruiterProfile"]["company"]) == {
        "id",
        "name",
        "website",
        "location",
        "isVerified",
    }


def test_admin_me_has_no_profiles(auth_client, admin_user):
    body = auth_client(admin_user).get(URL).json()
    assert body["role"] == "admin"
    assert body["jobSeekerProfile"] is None and body["recruiterProfile"] is None


def test_job_seeker_updates_profile(auth_client, job_seeker):
    response = auth_client(job_seeker).patch(
        URL,
        {
            "fullName": "New Name",
            "headline": "Backend dev",
            "cardVisible": False,
            "phone": "0712345678",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fullName"] == "New Name"
    assert body["phone"] == "+254712345678"
    assert body["jobSeekerProfile"]["headline"] == "Backend dev"
    assert body["jobSeekerProfile"]["cardVisible"] is False


def test_recruiter_updates_job_title(auth_client, recruiter):
    body = auth_client(recruiter).patch(URL, {"jobTitle": "Head of Talent"}).json()
    assert body["recruiterProfile"]["jobTitle"] == "Head of Talent"


def test_recruiter_cannot_set_job_seeker_fields(auth_client, recruiter):
    response = auth_client(recruiter).patch(URL, {"cardVisible": False})
    assert response.status_code == 400
    assert response.json()["fields"] == {"cardVisible": ["Not available for your role."]}


def test_clearing_phone(auth_client):
    user = UserFactory(phone="+254712345678")
    assert auth_client(user).patch(URL, {"phone": ""}).json()["phone"] is None


def test_phone_clash(auth_client, job_seeker):
    UserFactory(phone="+254712345678")
    response = auth_client(job_seeker).patch(URL, {"phone": "0712345678"})
    assert "phone" in response.json()["fields"]


def test_cannot_change_role_or_email(auth_client, job_seeker):
    body = auth_client(job_seeker).patch(URL, {"role": "admin", "email": "x@y.com"}).json()
    assert body["role"] == "job_seeker"
    assert body["email"] == job_seeker.email
