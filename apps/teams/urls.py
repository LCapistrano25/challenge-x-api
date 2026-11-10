from django.urls import path

from apps.teams.views import TeamCreateView, TeamDetailView

urlpatterns = [
    path("teams", TeamCreateView.as_view(), name="team-create"),
    path(
        "teams/<int:team_id>",
        TeamDetailView.as_view(),
        name="team-detail",
    ),
]