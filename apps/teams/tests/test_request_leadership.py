from unittest.mock import patch

import pytest

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    StudentFactory,
    TeacherCourseFactory,
    TeacherFactory,
    UserFactory,
)
from apps.notifications.models import NotificationType
from apps.projects.factories import ProjectFactory
from apps.teams.enums import MemberRole, RequestStatus
from apps.teams.factories import (
    LeadershipRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.use_cases.request_leadership import (
    LeadershipRequestRejected,
    request_leadership,
)

pytestmark = pytest.mark.django_db


def create_team_without_leader():
    team = TeamFactory(leader=False)
    project = ProjectFactory(team=team)
    student = StudentFactory(course=project.challenge.course)

    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    return team, project, student


def test_request_leadership_successfully():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
    )

    with patch("apps.teams.use_cases.request_leadership.create_notification") as notify:
        leadership_request = request_leadership(
            actor=student.user,
            team_id=team.id,
            justification="O antigo líder deixou a equipe.",
        )

    assert leadership_request.team == team
    assert leadership_request.requester == student
    assert leadership_request.justification == "O antigo líder deixou a equipe."
    assert leadership_request.status == RequestStatus.PENDING
    assert notify.call_count == 2

    notified_users = {call.kwargs["user"] for call in notify.call_args_list}

    assert notified_users == {student.user, teacher.user}


def test_request_leadership_without_formation_period():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
    )

    leadership_request = request_leadership(
        actor=student.user,
        team_id=team.id,
        justification="A equipe continua sem líder.",
    )

    assert leadership_request.status == RequestStatus.PENDING


def test_request_leadership_rejects_non_student():
    team, project, student = create_team_without_leader()
    admin = UserFactory(role=UserRole.ADMIN)

    with pytest.raises(
        LeadershipRequestRejected,
        match="Somente alunos podem solicitar a liderança.",
    ):
        request_leadership(
            actor=admin,
            team_id=team.id,
            justification="Solicitação de teste.",
        )


def test_request_leadership_rejects_student_without_profile():
    team, project, student = create_team_without_leader()
    student_user = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(
        LeadershipRequestRejected,
        match="O perfil de aluno não foi encontrado.",
    ):
        request_leadership(
            actor=student_user,
            team_id=team.id,
            justification="Solicitação de teste.",
        )


def test_request_leadership_rejects_nonexistent_team():
    student = StudentFactory()

    with pytest.raises(
        LeadershipRequestRejected,
        match="Equipe não encontrada.",
    ):
        request_leadership(
            actor=student.user,
            team_id=999999,
            justification="Solicitação de teste.",
        )


def test_request_leadership_rejects_non_member():
    team = TeamFactory(leader=False)
    ProjectFactory(team=team)
    student = StudentFactory()

    with pytest.raises(
        LeadershipRequestRejected,
        match="Somente integrantes ativos podem solicitar a liderança.",
    ):
        request_leadership(
            actor=student.user,
            team_id=team.id,
            justification="Solicitação de teste.",
        )


def test_request_leadership_rejects_team_with_active_leader():
    team = TeamFactory()
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    student = StudentFactory(course=leader.student.course)
    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )
    ProjectFactory(team=team)

    with pytest.raises(
        LeadershipRequestRejected,
        match="A equipe já possui um líder ativo.",
    ):
        request_leadership(
            actor=student.user,
            team_id=team.id,
            justification="Solicitação de teste.",
        )


def test_request_leadership_rejects_disqualified_team():
    team = TeamFactory(disqualified=True, leader=False)
    project = ProjectFactory(team=team)
    student = StudentFactory(course=project.challenge.course)

    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    with pytest.raises(
        LeadershipRequestRejected,
        match="Não é possível solicitar a liderança de uma equipe que não está ativa.",
    ):
        request_leadership(
            actor=student.user,
            team_id=team.id,
            justification="Solicitação de teste.",
        )


def test_request_leadership_rejects_blank_justification():
    team, project, student = create_team_without_leader()

    with pytest.raises(
        LeadershipRequestRejected,
        match="A justificativa da solicitação é obrigatória.",
    ):
        request_leadership(
            actor=student.user,
            team_id=team.id,
            justification="   ",
        )


def test_request_leadership_rejects_pending_request():
    team, project, student = create_team_without_leader()

    LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    with pytest.raises(
        LeadershipRequestRejected,
        match="Já existe uma solicitação de liderança pendente.",
    ):
        request_leadership(
            actor=student.user,
            team_id=team.id,
            justification="Nova solicitação.",
        )


def test_request_leadership_does_not_notify_inactive_teachers():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=False,
    )

    with patch("apps.teams.use_cases.request_leadership.create_notification") as notify:
        request_leadership(
            actor=student.user,
            team_id=team.id,
            justification="Solicitação de teste.",
        )

    notify.assert_called_once_with(
        user=student.user,
        notification_type=NotificationType.TEAM,
        title="Solicitação de liderança enviada",
        message=(
            f"Sua solicitação de liderança para a equipe {team.name} "
            "foi encaminhada aos professores."
        ),
        link=f"/equipes/{team.id}",
    )


def test_request_leadership_requires_project_challenge():
    team = TeamFactory(leader=False)
    student = StudentFactory()

    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    ProjectFactory(team=team, challenge=None)

    with pytest.raises(
        LeadershipRequestRejected,
        match=(
            "A equipe precisa possuir um desafio selecionado para solicitar liderança."
        ),
    ):
        request_leadership(
            actor=student.user,
            team_id=team.id,
            justification="Solicitação de teste.",
        )


def test_request_leadership_allows_new_request_after_rejection():
    team, project, student = create_team_without_leader()

    first_request = request_leadership(
        actor=student.user,
        team_id=team.id,
        justification="Solicitação inicial de liderança.",
    )

    first_request.status = RequestStatus.REJECTED
    first_request.save(update_fields=["status"])

    new_request = request_leadership(
        actor=student.user,
        team_id=team.id,
        justification="Nova solicitação após a rejeição.",
    )

    assert new_request.pk != first_request.pk
    assert new_request.status == RequestStatus.PENDING
    assert new_request.justification == "Nova solicitação após a rejeição."
