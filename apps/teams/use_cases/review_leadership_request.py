from http import HTTPStatus

from django.db import transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Teacher, TeacherCourse, User
from apps.core.exceptions import AppError
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.teams.enums import MemberRole, RequestStatus, TeamStatus
from apps.teams.models import LeadershipRequest, Team, TeamMember


class LeadershipRequestReviewRejected(AppError):
    """A decisão da solicitação de liderança foi rejeitada por uma regra de negócio."""

    code = "leadership_request_review_rejected"
    default_message = "A decisão da solicitação de liderança foi rejeitada."
    http_status = HTTPStatus.CONFLICT


class LeadershipRequestReviewNotFound(LeadershipRequestReviewRejected):
    code = "not_found"
    http_status = HTTPStatus.NOT_FOUND


class LeadershipRequestReviewInvalid(LeadershipRequestReviewRejected):
    code = "validation_error"
    http_status = HTTPStatus.BAD_REQUEST


@transaction.atomic
def review_leadership_request(
    *,
    actor: User,
    leadership_request_id: int,
    status: RequestStatus,
    decision_justification: str,
) -> LeadershipRequest:
    """Aprova ou rejeita uma solicitação de liderança por um professor."""
    if actor.role != UserRole.TEACHER:
        raise LeadershipRequestReviewRejected(
            "Somente professores podem decidir solicitações de liderança."
        )

    teacher = Teacher.objects.filter(user=actor).first()

    if teacher is None:
        raise LeadershipRequestReviewNotFound(
            "O perfil de professor não foi encontrado."
        )

    decision_justification = decision_justification.strip()

    if not decision_justification:
        raise LeadershipRequestReviewInvalid(
            "A justificativa da decisão é obrigatória."
        )

    request_ref = (
        LeadershipRequest.objects.filter(pk=leadership_request_id)
        .values("team_id")
        .first()
    )

    if request_ref is None:
        raise LeadershipRequestReviewNotFound("Solicitação não encontrada.")

    team = Team.objects.select_for_update().filter(pk=request_ref["team_id"]).first()

    if team is None:
        raise LeadershipRequestReviewNotFound("Equipe não encontrada.")

    leadership_request = (
        LeadershipRequest.objects.select_for_update()
        .select_related("requester__user", "team")
        .filter(pk=leadership_request_id, team=team)
        .first()
    )

    if leadership_request is None:
        raise LeadershipRequestReviewNotFound("Solicitação não encontrada.")

    if leadership_request.status != RequestStatus.PENDING:
        raise LeadershipRequestReviewRejected(
            "Esta solicitação não está mais pendente."
        )

    if team.status != TeamStatus.ACTIVE:
        raise LeadershipRequestReviewRejected(
            "Não é possível decidir solicitações de equipes desclassificadas."
        )

    allowed = TeacherCourse.objects.filter(
        teacher=teacher,
        active=True,
        course__challenges__projects__team_id=team.id,
    ).exists()

    if not allowed:
        raise LeadershipRequestReviewRejected(
            "O professor não está vinculado ao curso do desafio desta equipe."
        )

    if TeamMember.objects.filter(
        team=team,
        role=MemberRole.LEADER,
        active=True,
    ).exists():
        raise LeadershipRequestReviewRejected("A equipe já possui um líder ativo.")

    requester_membership = (
        TeamMember.objects.select_for_update()
        .filter(
            team=team,
            student=leadership_request.requester,
            active=True,
        )
        .first()
    )

    if requester_membership is None:
        raise LeadershipRequestReviewRejected(
            "O solicitante não é mais um integrante ativo da equipe."
        )

    now = timezone.now()

    if status == RequestStatus.APPROVED:
        TeamMember.objects.filter(
            team=team,
            role=MemberRole.LEADER,
            active=True,
        ).exclude(
            pk=requester_membership.pk,
        ).update(
            role=MemberRole.MEMBER,
            updated_at=now,
        )

        requester_membership.role = MemberRole.LEADER
        requester_membership.save(update_fields=["role", "updated_at"])

        leadership_request.status = RequestStatus.APPROVED
        notification_title = "Solicitação de liderança aprovada"
        notification_message = (
            f"Sua solicitação de liderança para a equipe {team.name} foi aprovada."
        )
        team_message = (
            f"{leadership_request.requester.user.name} "
            f"assumiu a liderança da equipe {team.name}."
        )
    else:
        leadership_request.status = RequestStatus.REJECTED
        notification_title = "Solicitação de liderança rejeitada"
        notification_message = (
            f"Sua solicitação de liderança para a equipe {team.name} foi rejeitada."
        )
        team_message = (
            f"A solicitação de liderança da equipe {team.name} foi rejeitada."
        )

    leadership_request.teacher = teacher
    leadership_request.decision_justification = decision_justification
    leadership_request.decided_at = now
    leadership_request.save(
        update_fields=[
            "status",
            "teacher",
            "decision_justification",
            "decided_at",
            "updated_at",
        ]
    )

    create_notification(
        user=leadership_request.requester.user,
        notification_type=NotificationType.TEAM,
        title=notification_title,
        message=notification_message,
        link=f"/equipes/{team.id}",
    )

    active_members = (
        TeamMember.objects.filter(team=team, active=True)
        .exclude(student=leadership_request.requester)
        .select_related("student__user")
    )

    for membership in active_members:
        create_notification(
            user=membership.student.user,
            notification_type=NotificationType.TEAM,
            title="Decisão sobre liderança da equipe",
            message=team_message,
            link=f"/equipes/{team.id}",
        )

    return leadership_request
