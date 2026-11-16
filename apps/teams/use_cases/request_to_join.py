from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.editions.enums import StageKind
from apps.editions.models import Stage
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.teams.enums import MemberRole, RequestStatus, TeamStatus
from apps.teams.models import JoinRequest, Team, TeamMember


class JoinRequestRejected(Exception):
    """A solicitação de entrada não pôde ser realizada por uma regra de negócio."""


@transaction.atomic
def request_to_join(
    *,
    actor: User,
    team_id: int,
) -> JoinRequest:
    """Registra uma solicitação de entrada do aluno em uma equipe."""
    if actor.role != UserRole.STUDENT:
        raise JoinRequestRejected("Somente alunos podem solicitar entrada em equipes.")

    student = Student.objects.filter(user=actor).first()

    if student is None:
        raise JoinRequestRejected("O perfil de aluno não foi encontrado.")

    if not actor.is_active or not actor.email_confirmed:
        raise JoinRequestRejected("O cadastro do aluno deve estar ativo e confirmado.")

    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise JoinRequestRejected("Equipe não encontrada.")

    if team.status != TeamStatus.ACTIVE:
        raise JoinRequestRejected(
            "Não é possível solicitar entrada em uma equipe desclassificada."
        )

    now = timezone.now()

    formation_open = Stage.objects.filter(
        edition=team.edition,
        kind=StageKind.FORMATION,
        starts_at__lte=now,
        ends_at__gte=now,
    ).exists()

    if not formation_open:
        raise JoinRequestRejected(
            "Não existe prazo de formação aberto para esta equipe."
        )

    current_members = TeamMember.objects.filter(
        team=team,
        active=True,
    ).count()

    if current_members >= team.edition.max_members:
        raise JoinRequestRejected("A equipe já atingiu o limite máximo de integrantes.")

    already_in_team = TeamMember.objects.filter(
        edition=team.edition,
        student=student,
        active=True,
    ).exists()

    if already_in_team:
        raise JoinRequestRejected(
            "O aluno já participa de uma equipe ativa nesta edição."
        )

    pending_request = JoinRequest.objects.filter(
        team=team,
        student=student,
        status=RequestStatus.PENDING,
    ).exists()

    if pending_request:
        raise JoinRequestRejected(
            "Já existe uma solicitação pendente para esta equipe."
        )

    leader_membership = (
        TeamMember.objects.select_related("student__user")
        .filter(
            team=team,
            role=MemberRole.LEADER,
            active=True,
        )
        .first()
    )

    if leader_membership is None:
        raise JoinRequestRejected("A equipe não possui um líder ativo.")

    try:
        with transaction.atomic():
            join_request = JoinRequest.objects.create(
                team=team,
                student=student,
            )
    except IntegrityError as error:
        raise JoinRequestRejected(
            "Não foi possível registrar a solicitação. "
            "Verifique se já existe uma solicitação pendente."
        ) from error

    create_notification(
        user=leader_membership.student.user,
        notification_type=NotificationType.TEAM,
        title="Nova solicitação para equipe",
        message=f"Um aluno solicitou entrada na equipe {team.name}.",
        link=f"/equipes/{team.id}",
    )

    return join_request
