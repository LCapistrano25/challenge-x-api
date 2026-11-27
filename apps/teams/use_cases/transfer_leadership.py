from http import HTTPStatus

from django.db import transaction

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.core.exceptions import BusinessRuleViolation
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.models import Team, TeamMember


class LeadershipTransferRejected(BusinessRuleViolation):
    """A transferência de liderança foi rejeitada por uma regra de negócio."""

    code = "leadership_transfer_rejected"
    http_status = HTTPStatus.CONFLICT


class LeadershipTransferNotFound(LeadershipTransferRejected):
    """Equipe ou perfil de aluno não encontrado."""

    code = "not_found"
    http_status = HTTPStatus.NOT_FOUND


class LeadershipTransferPermissionDenied(LeadershipTransferRejected):
    """Quem pede não é o líder ativo da equipe."""

    code = "not_team_leader"
    http_status = HTTPStatus.FORBIDDEN


class LeadershipTransferInvalidMember(LeadershipTransferRejected):
    """O destinatário não é outro integrante ativo da equipe: 400 pelo contrato."""

    code = "validation_error"
    http_status = HTTPStatus.BAD_REQUEST


class LeadershipTransferTeamDisqualified(LeadershipTransferRejected):
    code = "team_disqualified"


@transaction.atomic
def transfer_leadership(
    *,
    actor: User,
    team_id: int,
    member_id: int,
) -> TeamMember:
    """Transfere a liderança para outro integrante ativo da mesma equipe (RF27).

    `member_id` é o vínculo (team_member) do novo líder, como no contrato.
    """
    if actor.role != UserRole.STUDENT:
        raise LeadershipTransferRejected("Somente alunos podem transferir a liderança.")

    current_student = Student.objects.filter(user=actor).first()

    if current_student is None:
        raise LeadershipTransferNotFound("O perfil de aluno não foi encontrado.")

    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise LeadershipTransferNotFound("Equipe não encontrada.")

    if team.status != TeamStatus.ACTIVE:
        raise LeadershipTransferTeamDisqualified(
            "Não é possível transferir a liderança de uma equipe desclassificada."
        )

    current_membership = (
        TeamMember.objects.select_for_update()
        .filter(
            team=team,
            student=current_student,
            role=MemberRole.LEADER,
            active=True,
        )
        .first()
    )

    if current_membership is None:
        raise LeadershipTransferPermissionDenied(
            "Somente o líder ativo da equipe pode transferir a liderança."
        )

    new_leader_membership = (
        TeamMember.objects.select_for_update()
        .select_related("student__user")
        .filter(
            pk=member_id,
            team=team,
            active=True,
            role=MemberRole.MEMBER,
        )
        .first()
    )

    if new_leader_membership is None:
        raise LeadershipTransferInvalidMember(
            "O novo líder deve ser outro integrante ativo da equipe."
        )

    current_membership.role = MemberRole.MEMBER
    current_membership.save(update_fields=["role", "updated_at"])

    new_leader_membership.role = MemberRole.LEADER
    new_leader_membership.save(update_fields=["role", "updated_at"])

    members = TeamMember.objects.filter(
        team=team,
        active=True,
    ).select_related("student__user")

    for member in members:
        create_notification(
            user=member.student.user,
            notification_type=NotificationType.TEAM,
            title="Liderança da equipe transferida",
            message=(
                f"A liderança da equipe {team.name} foi transferida "
                f"para {new_leader_membership.student.user.name}."
            ),
            link=f"/equipes/{team.id}",
        )

    return new_leader_membership
