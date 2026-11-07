from django.urls import path

from . import views

urlpatterns = [
    path("admin/stats", views.StatsView.as_view(), name="admin-stats"),
    path("admin/recruiters", views.RecruiterQueueView.as_view(), name="admin-recruiters"),
    path(
        "admin/recruiters/<uuid:public_id>/approve",
        views.RecruiterReviewView.as_view(action="approve"),
        name="admin-recruiter-approve",
    ),
    path(
        "admin/recruiters/<uuid:public_id>/reject",
        views.RecruiterReviewView.as_view(action="reject"),
        name="admin-recruiter-reject",
    ),
    path("admin/users", views.UserListView.as_view(), name="admin-users"),
    path("admin/users/<uuid:public_id>", views.UserDetailView.as_view(), name="admin-user"),
    path(
        "admin/notification-deliveries", views.DeliveryListView.as_view(), name="admin-deliveries"
    ),
    path(
        "admin/notification-deliveries/<uuid:public_id>/retry",
        views.DeliveryRetryView.as_view(),
        name="admin-delivery-retry",
    ),
    path("admin/audit-log", views.AuditLogView.as_view(), name="admin-audit-log"),
    path("admin/feedback/held", views.HeldFeedbackView.as_view(), name="admin-held-feedback"),
    path(
        "admin/feedback/<uuid:public_id>/release",
        views.HeldFeedbackDecisionView.as_view(action="release"),
        name="admin-feedback-release",
    ),
    path(
        "admin/feedback/<uuid:public_id>/reject",
        views.HeldFeedbackDecisionView.as_view(action="reject"),
        name="admin-feedback-reject",
    ),
    path("admin/skills", views.SkillAdminListView.as_view(), name="admin-skills"),
    path("admin/skills/<slug:slug>", views.SkillAdminDetailView.as_view(), name="admin-skill"),
    path(
        "admin/dependency-mappings",
        views.DependencyMappingListView.as_view(),
        name="admin-mappings",
    ),
    path(
        "admin/dependency-mappings/<str:ecosystem>/<path:package>",
        views.DependencyMappingDetailView.as_view(),
        name="admin-mapping",
    ),
]
