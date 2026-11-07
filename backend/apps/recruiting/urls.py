from django.urls import path

from . import views

urlpatterns = [
    path("candidates", views.CandidateListView.as_view(), name="candidates"),
    path(
        "candidates/<str:github_login>",
        views.CandidateDetailView.as_view(),
        name="candidate-detail",
    ),
    path(
        "candidates/<str:github_login>/feedback",
        views.CandidateFeedbackView.as_view(),
        name="candidate-feedback",
    ),
    path("feedback", views.FeedbackListView.as_view(), name="feedback"),
    path("feedback/<uuid:public_id>/read", views.FeedbackReadView.as_view(), name="feedback-read"),
    path("jobs", views.JobListCreateView.as_view(), name="jobs"),
    path("jobs/<uuid:public_id>", views.JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:public_id>/matches", views.JobMatchesView.as_view(), name="job-matches"),
    path("jobs/<uuid:public_id>/match/me", views.JobMatchMeView.as_view(), name="job-match-me"),
    path("shortlists", views.ShortlistListCreateView.as_view(), name="shortlists"),
    path(
        "shortlists/<uuid:public_id>", views.ShortlistDetailView.as_view(), name="shortlist-detail"
    ),
    path("me/profile-views", views.ProfileViewsView.as_view(), name="profile-views"),
]
