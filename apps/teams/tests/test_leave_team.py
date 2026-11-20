from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.editions.enums import StageKind
from apps.editions.factories import StageFactory
from apps.notifications.models import NotificationType
from apps.projects.factories import ProjectFactory
from apps.teams.enums import InvitationStatus, MemberRole, RequestStatus, TeamStatus
from apps.teams.factories import (
    InvitationFactory,
    JoinRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.use_cases.leave_team import (
    LeaveTeamRejected,
    leave_team,
)

pytestmark = pytest.mark.django_db


def create_open_formation(edition):
    now = timezone.now()

    return StageFactory(
        edition=edition,
        kind=StageKind.FORMATION,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )


def test_leave_team_successfully():
    team = TeamFactory()
    create_open_formation(team.edition)

    student = StudentFactory(
        course=team.members.get(
            role=MemberRole.LEADER,
            active=True,
        ).student.course
    )

    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    membership = leave_team(
        actor=student.user,
        team_id=team.id,
    )

    membership.refresh_from_db()

    assert membership.active is False
    assert membership.left_at is not None
    assert membership.team_id == team.id
    assert membership.student == student


def test_leave_team_rejects_leader_when_there_are_other_members():
    team = TeamFactory()
    create_open_formation(team.edition)
    TeamMemberFactory(team=team, role=MemberRole.MEMBER)

    leader_membership = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    with pytest.raises(
        LeaveTeamRejected,
        match="Transfira a liderança antes de sair da equipe.",
    ):
        leave_team(
            actor=leader_membership.student.user,
            team_id=team.id,
        )

    leader_membership.refresh_from_db()

    assert leader_membership.active is True
    assert leader_membership.left_at is None
    team.refresh_from_db()
    assert team.status == TeamStatus.ACTIVE


def test_lider_sozinho_sai_e_desfaz_a_equipe():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    convite = InvitationFactory(team=team)
    pedido = JoinRequestFactory(team=team)

    leave_team(actor=leader.student.user, team_id=team.id)

    leader.refresh_from_db()
    team.refresh_from_db()
    convite.refresh_from_db()
    pedido.refresh_from_db()
    assert leader.active is False and leader.left_at is not None
    assert team.status == TeamStatus.DISBANDED
    assert convite.status == InvitationStatus.CANCELLED
    assert pedido.status == RequestStatus.CANCELLED


def test_quem_esperava_resposta_e_avisado_quando_a_equipe_e_desfeita():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    convidado = InvitationFactory(team=team).student
    solicitante = JoinRequestFactory(team=team).student

    with patch("apps.teams.use_cases.leave_team.create_notification") as notify:
        leave_team(actor=leader.student.user, team_id=team.id)

    avisados = {call.kwargs["user"] for call in notify.call_args_list}
    assert avisados == {convidado.user, solicitante.user}
    assert all(c.kwargs["title"] == "Equipe desfeita" for c in notify.call_args_list)


def test_aluno_que_desfez_a_equipe_pode_entrar_em_outra():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    leave_team(actor=leader.student.user, team_id=team.id)

    outra = TeamFactory(edition=team.edition, leader=False)
    novo = TeamMemberFactory(team=outra, student=leader.student)

    assert novo.active is True


def test_leave_team_rejects_non_member():
    team = TeamFactory()
    create_open_formation(team.edition)

    student = StudentFactory()

    with pytest.raises(
        LeaveTeamRejected,
        match="O aluno não possui vínculo ativo com esta equipe.",
    ):
        leave_team(
            actor=student.user,
            team_id=team.id,
        )


def test_leave_team_rejects_when_formation_is_closed():
    team = TeamFactory()

    StageFactory(
        edition=team.edition,
        kind=StageKind.FORMATION,
        starts_at=timezone.now() - timedelta(days=3),
        ends_at=timezone.now() - timedelta(days=1),
    )

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    student = StudentFactory(course=leader.student.course)

    membership = TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    with pytest.raises(
        LeaveTeamRejected,
        match="Não existe prazo de formação aberto para esta equipe.",
    ):
        leave_team(
            actor=student.user,
            team_id=team.id,
        )

    membership.refresh_from_db()

    assert membership.active is True
    assert membership.left_at is None


def test_leave_team_rejects_nonexistent_team():
    student = StudentFactory()

    with pytest.raises(LeaveTeamRejected, match="Equipe não encontrada."):
        leave_team(
            actor=student.user,
            team_id=999999,
        )


def test_leave_team_rejects_student_without_profile():
    team = TeamFactory()
    create_open_formation(team.edition)

    student_user = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(
        LeaveTeamRejected,
        match="O perfil de aluno não foi encontrado.",
    ):
        leave_team(
            actor=student_user,
            team_id=team.id,
        )


def test_leave_team_invalidates_challenge_without_course_representative():
    team = TeamFactory()
    create_open_formation(team.edition)

    student = StudentFactory()
    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    project = ProjectFactory(
        team=team,
        challenge__course=student.course,
    )

    with patch("apps.teams.use_cases.leave_team._invalidate_challenge") as invalidate:
        leave_team(
            actor=student.user,
            team_id=team.id,
        )

    invalidate.assert_called_once_with(project)


def test_leave_team_notifies_remaining_members():
    team = TeamFactory()
    create_open_formation(team.edition)

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    student = StudentFactory()
    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    with patch("apps.teams.use_cases.leave_team.create_notification") as notify:
        leave_team(
            actor=student.user,
            team_id=team.id,
        )

    notify.assert_called_once()

    notification = notify.call_args.kwargs

    assert notification["user"] == leader.student.user
    assert notification["notification_type"] == NotificationType.TEAM
    assert notification["title"] == "Integrante saiu da equipe"
