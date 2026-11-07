from django.urls import path

from . import views

urlpatterns = [
    path("analyses", views.AnalysisListCreateView.as_view(), name="analyses"),
    path("analyses/<uuid:public_id>", views.AnalysisDetailView.as_view(), name="analysis-detail"),
    path("cards/<str:github_login>", views.CardView.as_view(), name="card"),
    path("me/claimed-skills", views.ClaimedSkillsView.as_view(), name="claimed-skills"),
]
