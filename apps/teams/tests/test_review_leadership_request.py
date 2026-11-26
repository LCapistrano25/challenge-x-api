from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    StudentFactory,
    TeacherCourseFactory,
    TeacherFactory,
    UserFactory,
)
from apps.projects.factories import ProjectFactory
from apps.teams.enums import MemberRole, RequestStatus, TeamStatus
from apps.teams.factories import (
    LeadershipRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.use_cases.review_leadership_request import (
    LeadershipRequestReviewRejected,
    review_leadership_request,
)

pytestmark = pytest.mark.django_db


def create_leadership_request():
    team = TeamFactory(leader=False)
    project = ProjectFactory(team=team)
    requester = StudentFactory(course=project.challenge.course)
    TeamMemberFactory(
        team=team,
        student=requester,
        role=MemberRole.MEMBER,
    )
    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=requester,
    )
    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
    )
    return team, project, requester, leadership_request, teacher


def test_review_leadership_request_approves_and_promotes_requester():
    team, project, requester, leadership_request, teacher = create_leadership_request()

    with patch(
        "apps.teams.use_cases.review_leadership_request.create_notification"
    ) as notify:
        result = review_leadership_request(
            actor=teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="O pedido foi considerado procedente.",
        )

    requester_membership = team.members.get(student=requester)

    assert result.status == RequestStatus.APPROVED
    assert result.teacher == teacher
    assert result.decision_justification == "O pedido foi considerado procedente."
    assert result.decided_at is not None
    assert requester_membership.role == MemberRole.LEADER
    assert requester_membership.active is True
    assert notify.call_count == 1


def test_review_leadership_request_rejects_and_keeps_team_without_leader():
    team, project, requester, leadership_request, teacher = create_leadership_request()

    with patch(
        "apps.teams.use_cases.review_leadership_request.create_notification"
    ) as notify:
        result = review_leadership_request(
            actor=teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.REJECTED,
            decision_justification="A justificativa apresentada não foi suficiente.",
        )

    assert result.status == RequestStatus.REJECTED
    assert result.teacher == teacher
    assert result.decided_at is not None
    assert not team.members.filter(
        role=MemberRole.LEADER,
        active=True,
    ).exists()
    assert notify.call_count == 1


def test_review_leadership_request_notifies_other_active_members():
    team, project, requester, leadership_request, teacher = create_leadership_request()
    other_student = StudentFactory(course=project.challenge.course)
    TeamMemberFactory(team=team, student=other_student)

    with patch(
        "apps.teams.use_cases.review_leadership_request.create_notification"
    ) as notify:
        review_leadership_request(
            actor=teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )

    notified_users = {call.kwargs["user"] for call in notify.call_args_list}
    assert notified_users == {requester.user, other_student.user}

    notifications_by_user = {
        call.kwargs["user"]: call.kwargs for call in notify.call_args_list
    }

    assert notifications_by_user[requester.user]["title"] == (
        "Solicitação de liderança aprovada"
    )
    assert notifications_by_user[requester.user]["message"] == (
        f"Sua solicitação de liderança para a equipe {team.name} foi aprovada."
    )

    assert notifications_by_user[other_student.user]["title"] == (
        "Decisão sobre liderança da equipe"
    )
    assert notifications_by_user[other_student.user]["message"] == (
        f"{requester.user.name} assumiu a liderança da equipe {team.name}."
    )


def test_review_leadership_request_rejects_non_teacher():
    team, project, requester, leadership_request, teacher = create_leadership_request()
    student_user = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="Somente professores podem decidir solicitações de liderança.",
    ):
        review_leadership_request(
            actor=student_user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )


def test_review_leadership_request_rejects_teacher_without_profile():
    team, project, requester, leadership_request, teacher = create_leadership_request()
    teacher_user = UserFactory(role=UserRole.TEACHER)

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="O perfil de professor não foi encontrado.",
    ):
        review_leadership_request(
            actor=teacher_user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )


def test_review_leadership_request_rejects_teacher_without_course_link():
    team, project, requester, leadership_request, teacher = create_leadership_request()
    other_teacher = TeacherFactory()

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="O professor não está vinculado ao curso do desafio desta equipe.",
    ):
        review_leadership_request(
            actor=other_teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )


def test_review_leadership_request_rejects_nonexistent_request():
    teacher = TeacherFactory()

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="Solicitação não encontrada.",
    ):
        review_leadership_request(
            actor=teacher.user,
            leadership_request_id=999999,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )


def test_review_leadership_request_rejects_already_decided_request():
    team, project, requester, leadership_request, teacher = create_leadership_request()
    leadership_request.status = RequestStatus.REJECTED
    leadership_request.save(update_fields=["status"])

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="Esta solicitação não está mais pendente.",
    ):
        review_leadership_request(
            actor=teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )


def test_review_leadership_request_rejects_disqualified_team():
    team, project, requester, leadership_request, teacher = create_leadership_request()

    team.status = TeamStatus.DISQUALIFIED
    team.disqualification_reason = "Desclassificada no teste."
    team.disqualified_at = timezone.now()

    team.disqualified_by = UserFactory(role=UserRole.ADMIN)
    team.save(
        update_fields=[
            "status",
            "disqualification_reason",
            "disqualified_at",
            "disqualified_by",
        ]
    )

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="Não é possível decidir solicitações de equipes desclassificadas.",
    ):
        review_leadership_request(
            actor=teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )


def test_review_leadership_request_rejects_blank_justification():
    team, project, requester, leadership_request, teacher = create_leadership_request()

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="A justificativa da decisão é obrigatória.",
    ):
        review_leadership_request(
            actor=teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="   ",
        )


def test_review_leadership_request_rejects_requester_not_active_member():
    team, project, requester, leadership_request, teacher = create_leadership_request()
    membership = team.members.get(student=requester)
    membership.active = False
    membership.left_at = timezone.now()
    membership.save(update_fields=["active", "left_at"])

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="O solicitante não é mais um integrante ativo da equipe.",
    ):
        review_leadership_request(
            actor=teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )


def test_review_leadership_request_rejects_team_with_active_leader():
    team, project, requester, leadership_request, teacher = create_leadership_request()
    other_student = StudentFactory(course=project.challenge.course)
    TeamMemberFactory(
        team=team,
        student=other_student,
        role=MemberRole.LEADER,
    )

    with pytest.raises(
        LeadershipRequestReviewRejected,
        match="A equipe já possui um líder ativo.",
    ):
        review_leadership_request(
            actor=teacher.user,
            leadership_request_id=leadership_request.id,
            status=RequestStatus.APPROVED,
            decision_justification="Pedido aprovado.",
        )


def test_review_leadership_request_preserves_inactive_former_leader_role():
    team, project, requester, leadership_request, teacher = create_leadership_request()

    former_leader = StudentFactory(course=project.challenge.course)
    former_membership = TeamMemberFactory(
        team=team,
        student=former_leader,
        role=MemberRole.LEADER,
    )
    former_membership.active = False
    former_membership.left_at = timezone.now()
    former_membership.save(update_fields=["active", "left_at"])

    result = review_leadership_request(
        actor=teacher.user,
        leadership_request_id=leadership_request.id,
        status=RequestStatus.APPROVED,
        decision_justification="Solicitação aprovada após análise.",
    )

    former_membership.refresh_from_db()
    requester_membership = team.members.get(student=requester)

    assert result.status == RequestStatus.APPROVED
    assert requester_membership.role == MemberRole.LEADER
    assert former_membership.role == MemberRole.LEADER
    assert former_membership.active is False
