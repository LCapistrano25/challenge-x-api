from django.urls import path

from apps.projects import views

urlpatterns = [
    path(
        "<int:team_id>/project/options",
        views.ProjectOptionsView.as_view(),
        name="project-options",
    ),
    path("<int:team_id>/project", views.TeamProjectView.as_view(), name="project"),
    path(
        "<int:team_id>/project/challenge",
        views.ProjectChallengeView.as_view(),
        name="project-challenge",
    ),
    path(
        "<int:team_id>/project/details",
        views.ProjectDetailsView.as_view(),
        name="project-details",
    ),
]
