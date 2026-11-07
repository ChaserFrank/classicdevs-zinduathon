"""Root URL configuration. Everything public lives under /api/v1/; Django admin is moved off
/admin/ so it doesn't collide with the admin *API* at /api/v1/admin/."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

api_v1 = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    # Docs are not throttled: judges and teammates browse them a lot at the venue.
    path("schema/", SpectacularAPIView.as_view(throttle_classes=[]), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="schema", throttle_classes=[]),
        name="swagger-ui",
    ),
    path(
        "redoc/", SpectacularRedocView.as_view(url_name="schema", throttle_classes=[]), name="redoc"
    ),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]

handler404 = "apps.core.views.json_404"
handler500 = "apps.core.views.json_500"
