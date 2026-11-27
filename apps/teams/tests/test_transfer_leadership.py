from unittest.mock import patch

import pytest

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.notifications.models import NotificationType
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamFactory, TeamMemberFactory
from apps.teams.use_cases.transfer_leadership import (
    LeadershipTransferRejected,
    transfer_leadership,
)

pytestmark = pytest.mark.django_db


def test_transfer_leadership_successfully():
    team = TeamFactory()

    current_leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    new_student = StudentFactory(course=current_leader.student.course)

    new_membership = TeamMemberFactory(
        team=team,
        student=new_student,
        role=MemberRole.MEMBER,
    )

    result = transfer_leadership(
        actor=current_leader.student.user,
        team_id=team.id,
        member_id=new_membership.pk,
    )

    current_leader.refresh_from_db()
    new_membership.refresh_from_db()

    assert result.pk == new_membership.pk
    assert current_leader.role == MemberRole.MEMBER
    assert current_leader.active is True
    assert current_leader.left_at is None
    assert new_membership.role == MemberRole.LEADER
    assert new_membership.active is True
    assert new_membership.left_at is None


def test_transfer_leadership_rejects_non_student():
    team = TeamFactory()
    admin = UserFactory(role=UserRole.ADMIN)

    target = StudentFactory()
    TeamMemberFactory(team=team, student=target)

    with pytest.raises(
        LeadershipTransferRejected,
        match="Somente alunos podem transferir a liderança.",
    ):
        transfer_leadership(
            actor=admin,
            team_id=team.id,
            member_id=999998,
        )


def test_transfer_leadership_rejects_student_without_profile():
    team = TeamFactory()
    student_user = UserFactory(role=UserRole.STUDENT)

    target = StudentFactory()
    TeamMemberFactory(team=team, student=target)

    with pytest.raises(
        LeadershipTransferRejected,
        match="O perfil de aluno não foi encontrado.",
    ):
        transfer_leadership(
            actor=student_user,
            team_id=team.id,
            member_id=999998,
        )


def test_transfer_leadership_rejects_nonexistent_team():
    student = StudentFactory()

    with pytest.raises(
        LeadershipTransferRejected,
        match="Equipe não encontrada.",
    ):
        transfer_leadership(
            actor=student.user,
            team_id=999999,
            member_id=999998,
        )


def test_transfer_leadership_rejects_non_leader():
    team = TeamFactory()

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    student = StudentFactory(course=leader.student.course)
    membership = TeamMemberFactory(team=team, student=student)

    with pytest.raises(
        LeadershipTransferRejected,
        match="Somente o líder ativo da equipe pode transferir a liderança.",
    ):
        transfer_leadership(
            actor=student.user,
            team_id=team.id,
            member_id=leader.pk,
        )

    membership.refresh_from_db()

    assert membership.role == MemberRole.MEMBER
    assert membership.active is True


def test_transfer_leadership_rejects_student_outside_team():
    team = TeamFactory()

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    outsider = StudentFactory(course=leader.student.course)

    with pytest.raises(
        LeadershipTransferRejected,
        match="O novo líder deve ser outro integrante ativo da equipe.",
    ):
        transfer_leadership(
            actor=leader.student.user,
            team_id=team.id,
            member_id=TeamMemberFactory(student=outsider).pk,
        )


def test_transfer_leadership_rejects_inactive_member():
    team = TeamFactory()

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    student = StudentFactory(course=leader.student.course)

    membership = TeamMemberFactory(
        team=team,
        student=student,
    )

    membership.active = False
    membership.left_at = membership.joined_at
    membership.save(update_fields=["active", "left_at", "updated_at"])

    with pytest.raises(
        LeadershipTransferRejected,
        match="O novo líder deve ser outro integrante ativo da equipe.",
    ):
        transfer_leadership(
            actor=leader.student.user,
            team_id=team.id,
            member_id=membership.pk,
        )


def test_transfer_leadership_rejects_team_without_another_member():
    team = TeamFactory()

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    with pytest.raises(
        LeadershipTransferRejected,
        match="O novo líder deve ser outro integrante ativo da equipe.",
    ):
        transfer_leadership(
            actor=leader.student.user,
            team_id=team.id,
            member_id=leader.pk,
        )

    leader.refresh_from_db()

    assert leader.role == MemberRole.LEADER
    assert leader.active is True


def test_transfer_leadership_notifies_all_active_members():
    team = TeamFactory()

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    new_student = StudentFactory(course=leader.student.course)

    new_membership = TeamMemberFactory(
        team=team,
        student=new_student,
        role=MemberRole.MEMBER,
    )

    with patch(
        "apps.teams.use_cases.transfer_leadership.create_notification"
    ) as notify:
        transfer_leadership(
            actor=leader.student.user,
            team_id=team.id,
            member_id=new_membership.pk,
        )

    assert notify.call_count == 2

    notified_users = {call.kwargs["user"] for call in notify.call_args_list}

    assert notified_users == {
        leader.student.user,
        new_student.user,
    }

    for call in notify.call_args_list:
        assert call.kwargs["notification_type"] == NotificationType.TEAM
        assert call.kwargs["title"] == "Liderança da equipe transferida"
        assert call.kwargs["link"] == f"/equipes/{team.id}"
