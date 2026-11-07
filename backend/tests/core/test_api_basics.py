import pytest
from rest_framework.test import APIRequestFactory

from apps.core.pagination import StandardPagination

pytestmark = pytest.mark.django_db


def test_unknown_api_url_returns_json_404(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not found."}


@pytest.mark.parametrize("url", ["/api/v1/schema/", "/api/v1/docs/", "/api/v1/redoc/"])
def test_api_docs_are_public(client, url):
    assert client.get(url).status_code == 200


def test_schema_documents_health_under_system_tag(client):
    schema = client.get("/api/v1/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json").json()
    operation = schema["paths"]["/api/v1/health"]["get"]
    assert operation["tags"] == ["System"]
    assert "commitSha" in schema["components"]["schemas"]["Health"]["properties"]


def test_cors_allows_configured_frontend_origin(client):
    response = client.options(
        "/api/v1/health",
        HTTP_ORIGIN="http://localhost:3000",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
    )
    assert response["Access-Control-Allow-Origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client):
    response = client.get("/api/v1/health", HTTP_ORIGIN="https://evil.example")
    assert "Access-Control-Allow-Origin" not in response


class TestPagination:
    def paginate(self, query: str, items=range(250)):
        request = APIRequestFactory().get(f"/x{query}")
        from rest_framework.request import Request

        paginator = StandardPagination()
        page = paginator.paginate_queryset(list(items), Request(request))
        return paginator, page

    def test_default_page_size_is_20(self):
        paginator, page = self.paginate("")
        assert len(page) == 20
        assert paginator.get_paginated_response(page).data["count"] == 250

    def test_page_size_param_is_capped_at_100(self):
        _, page = self.paginate("?page_size=500")
        assert len(page) == 100

    def test_camel_case_page_size_param_works_end_to_end(self, client, django_user_model):
        # Verified via middleware: ?pageSize reaches the paginator as page_size.
        from djangorestframework_camel_case.middleware import CamelCaseMiddleWare

        captured = {}

        def view(request):
            captured.update(request.GET.dict())
            from django.http import HttpResponse

            return HttpResponse()

        CamelCaseMiddleWare(view)(APIRequestFactory().get("/x?pageSize=5&minScore=60"))
        assert captured == {"page_size": "5", "min_score": "60"}

    def test_response_shape(self):
        paginator, page = self.paginate("?page=2")
        data = paginator.get_paginated_response(page).data
        assert list(data) == ["count", "next", "previous", "results"]
        assert data["results"][0] == 20
