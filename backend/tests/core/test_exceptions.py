"""The error shape is part of the API contract: {code, message, fields?}."""

import pytest
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.urls import path
from rest_framework import exceptions, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ApiError, api_exception_handler


class NoPublicRepos(ApiError):
    status_code = 422
    default_code = "no_public_repos"
    default_detail = "This GitHub account has no public repositories to analyse."


class _Nested(serializers.Serializer):
    phone_number = serializers.CharField()


class _Payload(serializers.Serializer):
    full_name = serializers.CharField(max_length=3)
    contact = _Nested()


class _ValidationView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        _Payload(data=request.data).is_valid(raise_exception=True)
        return Response({})


class _CrashView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request):
        raise RuntimeError("boom")


class _ProtectedView(APIView):
    def get(self, request):
        return Response({})


urlpatterns = [
    path("validate", _ValidationView.as_view()),
    path("crash", _CrashView.as_view()),
    path("protected", _ProtectedView.as_view()),
]


def handle(exc):
    return api_exception_handler(exc, {})


@pytest.fixture
def test_urls(settings):
    settings.ROOT_URLCONF = __name__


def test_validation_error_has_camel_case_fields(api_client, test_urls):
    response = api_client.post("/validate", {"fullName": "too long", "contact": {}}, format="json")

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Some fields are invalid."
    assert set(body["fields"]) == {"fullName", "contact.phoneNumber"}
    assert body["fields"]["fullName"] == ["Ensure this field has no more than 3 characters."]


def test_unauthenticated_request(api_client, test_urls):
    response = api_client.get("/protected")
    assert response.status_code == 401
    assert response.json() == {"code": "not_authenticated", "message": "Sign in to continue."}


def test_unhandled_exception_becomes_server_error_without_leaking_details(api_client, test_urls):
    api_client.raise_request_exception = False
    response = api_client.get("/crash")
    assert response.status_code == 500
    assert response.json()["code"] == "server_error"
    assert "boom" not in response.content.decode()


def test_domain_error_uses_its_own_code_and_status():
    response = handle(NoPublicRepos())
    assert response.status_code == 422
    assert response.data == {
        "code": "no_public_repos",
        "message": "This GitHub account has no public repositories to analyse.",
    }


def test_domain_error_message_can_be_overridden():
    assert handle(NoPublicRepos("No repos for ann")).data["message"] == "No repos for ann"


def test_permission_denied_keeps_specific_code():
    exc = exceptions.PermissionDenied(
        "Your recruiter account is awaiting approval.", code="recruiter_not_approved"
    )
    response = handle(exc)
    assert response.status_code == 403
    assert response.data["code"] == "recruiter_not_approved"


def test_generic_permission_denied():
    assert handle(exceptions.PermissionDenied()).data["code"] == "permission_denied"


def test_django_permission_denied_and_404_are_mapped():
    assert handle(DjangoPermissionDenied()).data["code"] == "permission_denied"
    response = handle(Http404())
    assert response.status_code == 404
    assert response.data == {"code": "not_found", "message": "Not found."}


def test_invalid_token_maps_to_token_invalid():
    exc = exceptions.AuthenticationFailed(
        {"detail": "Given token not valid", "code": "token_not_valid"}
    )
    response = handle(exc)
    assert response.status_code == 401
    assert response.data == {"code": "token_invalid", "message": "Given token not valid"}


def test_throttled_says_when_to_retry():
    response = handle(exceptions.Throttled(wait=42))
    assert response.status_code == 429
    assert response.data["code"] == "rate_limited"
    assert "42 seconds" in response.data["message"]


def test_non_field_and_list_errors_are_flattened():
    exc = exceptions.ValidationError({"non_field_errors": ["Bad combo"], "items": [{"x": ["bad"]}]})
    fields = handle(exc).data["fields"]
    assert fields == {"non_field_errors": ["Bad combo"], "items.0.x": ["bad"]}


def test_bare_string_validation_error():
    assert handle(exceptions.ValidationError("Nope")).data["fields"] == {"nonFieldErrors": ["Nope"]}


def test_method_not_allowed():
    response = handle(exceptions.MethodNotAllowed("PUT"))
    assert response.data["code"] == "method_not_allowed"
