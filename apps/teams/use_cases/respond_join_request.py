from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.teams.enums import (
    InvitationStatus,
    MemberRole,
    RequestStatus,
    TeamStatus,
)
from apps.teams.models import (
    Invitation,
    JoinRequest,
    Team,
    TeamMember,
)
from apps.teams.rules import is_formation_open_for_team


class JoinRequestResponseRejected(Exception):
    """A resposta à solicitação foi rejeitada por uma regra de negócio."""


@transaction.atomic
def respond_join_request(
    *,
    actor: User,
    join_request_id: int,
    approve: bool,
) -> JoinRequest:
    """Aprova ou rejeita uma solicitação de entrada em equipe."""
    if actor.role != UserRole.STUDENT:
        raise JoinRequestResponseRejected(
            "Somente alunos podem responder solicitações de entrada."
        )

    leader = Student.objects.filter(user=actor).first()

    if leader is None:
        raise JoinRequestResponseRejected("O perfil de aluno não foi encontrado.")

    request_ref = (
        JoinRequest.objects.filter(pk=join_request_id).values("team_id").first()
    )

    if request_ref is None:
        raise JoinRequestResponseRejected("Solicitação não encontrada.")

    team = Team.objects.select_for_update().filter(pk=request_ref["team_id"]).first()

    if team is None:
        raise JoinRequestResponseRejected("Equipe não encontrada.")

    join_request = (
        JoinRequest.objects.select_for_update()
        .select_related("student__user", "team", "team__edition")
        .filter(pk=join_request_id, team_id=team.pk)
        .first()
    )

    if join_request is None:
        raise JoinRequestResponseRejected("Solicitação não encontrada.")

    is_leader = TeamMember.objects.filter(
        team=team,
        student=leader,
        role=MemberRole.LEADER,
        active=True,
    ).exists()

    if not is_leader:
        raise JoinRequestResponseRejected(
            "Somente o líder ativo da equipe pode responder solicitações."
        )

    if join_request.status != RequestStatus.PENDING:
        raise JoinRequestResponseRejected("Esta solicitação não está mais pendente.")

    now = timezone.now()

    formation_open = is_formation_open_for_team(team, now)

    if not formation_open:
        raise JoinRequestResponseRejected(
            "Não existe prazo de formação aberto para esta equipe."
        )

    if team.status != TeamStatus.ACTIVE:
        raise JoinRequestResponseRejected(
            "Não é possível responder solicitações de equipes desclassificadas."
        )

    student = join_request.student

    if not approve:
        join_request.status = RequestStatus.REJECTED
        join_request.responded_at = now
        join_request.save(update_fields=["status", "responded_at", "updated_at"])

        create_notification(
            user=student.user,
            notification_type=NotificationType.TEAM,
            title="Solicitação recusada",
            message=(
                f"Sua solicitação para participar da equipe {team.name} foi recusada."
            ),
            link=f"/equipes/{team.id}",
        )

        return join_request

    if not student.user.is_active or not student.user.email_confirmed:
        raise JoinRequestResponseRejected(
            "O estudante não possui cadastro ativo e confirmado."
        )

    already_in_team = TeamMember.objects.filter(
        edition=team.edition,
        student=student,
        active=True,
    ).exists()

    if already_in_team:
        raise JoinRequestResponseRejected(
            "O estudante já participa de uma equipe ativa nesta edição."
        )

    current_members = TeamMember.objects.filter(
        team=team,
        active=True,
    ).count()

    if current_members >= team.edition.max_members:
        raise JoinRequestResponseRejected(
            "A equipe já atingiu o limite máximo de integrantes."
        )

    try:
        with transaction.atomic():
            TeamMember.objects.create(
                team=team,
                edition=team.edition,
                student=student,
                role=MemberRole.MEMBER,
            )
    except IntegrityError as error:
        raise JoinRequestResponseRejected(
            "Não foi possível aprovar a solicitação. "
            "O estudante pode já estar vinculado a outra equipe."
        ) from error

    join_request.status = RequestStatus.APPROVED
    join_request.responded_at = now
    join_request.save(update_fields=["status", "responded_at", "updated_at"])

    Invitation.objects.filter(
        student=student,
        team__edition=team.edition,
        status=InvitationStatus.PENDING,
    ).update(
        status=InvitationStatus.CANCELLED,
        updated_at=now,
    )

    JoinRequest.objects.filter(
        student=student,
        team__edition=team.edition,
        status=RequestStatus.PENDING,
    ).exclude(
        pk=join_request.pk,
    ).update(
        status=RequestStatus.CANCELLED,
        updated_at=now,
    )

    create_notification(
        user=student.user,
        notification_type=NotificationType.TEAM,
        title="Solicitação aprovada",
        message=f"Sua solicitação para participar da equipe {team.name} foi aprovada.",
        link=f"/equipes/{team.id}",
    )

    return join_request
