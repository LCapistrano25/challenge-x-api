from http import HTTPStatus

from django.db import IntegrityError, transaction

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, TeacherCourse, User
from apps.core.exceptions import AppError
from apps.editions.rules import ensure_edition_not_closed
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.teams.enums import MemberRole, RequestStatus, TeamStatus
from apps.teams.models import LeadershipRequest, Team, TeamMember


class LeadershipRequestRejected(AppError):
    """A solicitação de liderança foi rejeitada por uma regra de negócio."""

    code = "leadership_request_rejected"
    default_message = "A solicitação de liderança foi rejeitada."
    http_status = HTTPStatus.CONFLICT


class LeadershipRequestNotFound(LeadershipRequestRejected):
    code = "not_found"
    http_status = HTTPStatus.NOT_FOUND


class LeadershipRequestInvalid(LeadershipRequestRejected):
    code = "validation_error"
    http_status = HTTPStatus.BAD_REQUEST


class LeadershipRequestTeamHasLeader(LeadershipRequestRejected):
    code = "team_has_leader"
    default_message = "A equipe já possui um líder ativo."


class LeadershipRequestChallengeNotSelected(LeadershipRequestRejected):
    """Sem desafio não há professor do curso para decidir o pedido (#285)."""

    code = "challenge_not_selected"
    default_message = (
        "A equipe precisa possuir um desafio selecionado para solicitar liderança."
    )


class LeadershipRequestPendingExists(LeadershipRequestRejected):
    code = "leadership_request_pending_exists"
    default_message = "Já existe uma solicitação de liderança pendente."


@transaction.atomic
def request_leadership(
    *,
    actor: User,
    team_id: int,
    justification: str,
) -> LeadershipRequest:
    """Solicita a liderança de uma equipe ativa que esteja sem líder."""
    if actor.role != UserRole.STUDENT:
        raise LeadershipRequestRejected("Somente alunos podem solicitar a liderança.")

    student = Student.objects.filter(user=actor).first()

    if student is None:
        raise LeadershipRequestNotFound("O perfil de aluno não foi encontrado.")

    justification = justification.strip()

    if not justification:
        raise LeadershipRequestInvalid("A justificativa da solicitação é obrigatória.")

    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise LeadershipRequestNotFound("Equipe não encontrada.")

    ensure_edition_not_closed(team.edition)

    if team.status != TeamStatus.ACTIVE:
        raise LeadershipRequestRejected(
            "Não é possível solicitar a liderança de uma equipe que não está ativa."
        )

    membership = TeamMember.objects.filter(
        team=team,
        student=student,
        active=True,
    ).exists()

    if not membership:
        raise LeadershipRequestNotFound(
            "Somente integrantes ativos podem solicitar a liderança."
        )

    has_active_leader = TeamMember.objects.filter(
        team=team,
        role=MemberRole.LEADER,
        active=True,
    ).exists()

    if has_active_leader:
        raise LeadershipRequestTeamHasLeader()

    pending_request = LeadershipRequest.objects.filter(
        team=team,
        status=RequestStatus.PENDING,
    ).exists()

    if pending_request:
        raise LeadershipRequestPendingExists()

    project = getattr(team, "project", None)

    if project is None or project.challenge_id is None:
        raise LeadershipRequestChallengeNotSelected()

    try:
        with transaction.atomic():
            leadership_request = LeadershipRequest.objects.create(
                team=team,
                requester=student,
                justification=justification,
            )
    except IntegrityError as error:
        if LeadershipRequest.objects.filter(
            team=team,
            status=RequestStatus.PENDING,
        ).exists():
            raise LeadershipRequestPendingExists() from error

        raise LeadershipRequestRejected(
            "Não foi possível registrar a solicitação."
        ) from error

    teachers = TeacherCourse.objects.filter(
        course_id=project.challenge.course_id,
        active=True,
    ).select_related("teacher__user")

    for teacher_course in teachers:
        create_notification(
            user=teacher_course.teacher.user,
            notification_type=NotificationType.TEAM,
            title="Nova solicitação de liderança",
            message=(
                f"{student.user.name} solicitou a liderança da equipe {team.name}."
            ),
            link=f"/equipes/{team.id}",
        )

    create_notification(
        user=student.user,
        notification_type=NotificationType.TEAM,
        title="Solicitação de liderança enviada",
        message=(
            f"Sua solicitação de liderança para a equipe {team.name} "
            "foi encaminhada aos professores."
        ),
        link=f"/equipes/{team.id}",
    )

    return leadership_request
