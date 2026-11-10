from django.urls import path

from apps.teams.views import (
    InvitationResponseView,
    MyInvitationsView,
    TeamCreateView,
    TeamDetailView,
    TeamInvitationView,
)

urlpatterns = [
    path("teams", TeamCreateView.as_view(), name="team-create"),
    path(
        "teams/<int:team_id>",
        TeamDetailView.as_view(),
        name="team-detail",
    ),
    path(
        "teams/<int:team_id>/invitations",
        TeamInvitationView.as_view(),
        name="team-invitations",
    ),
    path(
        "me/invitations",
        MyInvitationsView.as_view(),
        name="my-invitations",
    ),
    path(
        "invitations/<int:invitation_id>/respond",
        InvitationResponseView.as_view(),
        name="invitation-respond",
    ),
]
