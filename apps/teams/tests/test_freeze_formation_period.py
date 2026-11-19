from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.editions.factories import StageFactory
from apps.projects.factories import ProjectFactory
from apps.teams.enums import InvitationStatus, MemberRole, TeamSituation
from apps.teams.factories import (
    InvitationFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.use_cases.freeze_formation_period import freeze_formation_period

pytestmark = pytest.mark.django_db


def create_closed_formation(edition):
    now = timezone.now()
    return StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(days=1),
    )


def test_freeze_formation_period_marks_complete_team():
    team = TeamFactory()
    create_closed_formation(team.edition)

    ProjectFactory(team=team)
    TeamMemberFactory(team=team, role=MemberRole.MEMBER)
    TeamMemberFactory(team=team, role=MemberRole.MEMBER)

    actor = UserFactory(role=UserRole.ADMIN)

    result = freeze_formation_period(actor=actor)

    team.refresh_from_db()

    assert team.situation == TeamSituation.COMPLETE
    assert result == {"frozen_teams": 1, "cancelled_invitations": 0}


def test_freeze_formation_period_marks_incomplete_team():
    team = TeamFactory()
    create_closed_formation(team.edition)

    actor = UserFactory(role=UserRole.ADMIN)

    result = freeze_formation_period(actor=actor)

    team.refresh_from_db()

    assert team.situation == TeamSituation.INCOMPLETE
    assert result == {"frozen_teams": 1, "cancelled_invitations": 0}


def test_freeze_formation_period_cancels_only_pending_invitations():
    team = TeamFactory()
    create_closed_formation(team.edition)

    pending = InvitationFactory(team=team)
    accepted = InvitationFactory(
        team=team,
        status=InvitationStatus.ACCEPTED,
        responded_at=timezone.now(),
    )
    declined = InvitationFactory(
        team=team,
        status=InvitationStatus.DECLINED,
        responded_at=timezone.now(),
    )

    actor = UserFactory(role=UserRole.ADMIN)

    result = freeze_formation_period(actor=actor)

    pending.refresh_from_db()
    accepted.refresh_from_db()
    declined.refresh_from_db()

    assert pending.status == InvitationStatus.CANCELLED
    assert pending.responded_at is not None
    assert accepted.status == InvitationStatus.ACCEPTED
    assert declined.status == InvitationStatus.DECLINED
    assert result == {"frozen_teams": 1, "cancelled_invitations": 1}


def test_freeze_formation_period_rejects_non_admin():
    actor = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(NotAdminActor):
        freeze_formation_period(actor=actor)


def test_freeze_formation_period_does_not_process_open_formation():
    team = TeamFactory()
    now = timezone.now()

    StageFactory(
        edition=team.edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )
    InvitationFactory(team=team)

    actor = UserFactory(role=UserRole.ADMIN)

    result = freeze_formation_period(actor=actor)

    team.refresh_from_db()
    invitation = team.invitations.get()

    assert team.situation is None
    assert invitation.status == InvitationStatus.PENDING
    assert result == {"frozen_teams": 0, "cancelled_invitations": 0}


def test_freeze_formation_period_is_idempotent():
    team = TeamFactory()
    create_closed_formation(team.edition)
    actor = UserFactory(role=UserRole.ADMIN)

    first_result = freeze_formation_period(actor=actor)
    second_result = freeze_formation_period(actor=actor)

    assert first_result["frozen_teams"] == 1
    assert second_result["frozen_teams"] == 0
    team.refresh_from_db()
    assert team.situation == TeamSituation.INCOMPLETE
