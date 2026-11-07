from django.urls import path

from . import views

urlpatterns = [
    path(
        "me/notification-preferences",
        views.PreferencesView.as_view(),
        name="notification-preferences",
    ),
    path("notifications", views.NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/read-all",
        views.NotificationReadAllView.as_view(),
        name="notifications-read-all",
    ),
    path(
        "notifications/<uuid:public_id>/read",
        views.NotificationReadView.as_view(),
        name="notification-read",
    ),
    path(
        "webhooks/thrivewave/delivery",
        views.DeliveryReportView.as_view(),
        name="thrivewave-delivery",
    ),
    path("webhooks/thrivewave/inbound", views.InboundSmsView.as_view(), name="thrivewave-inbound"),
]
