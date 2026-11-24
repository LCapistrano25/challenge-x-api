from django.urls import path

from apps.projects import views

urlpatterns = [
    path(
        "<int:team_id>/deadline-extensions",
        views.TeamDeadlineExtensionView.as_view(),
        name="team-deadline-extensions",
    ),
]
