from http import HTTPStatus

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.core.exceptions import BusinessRuleViolation
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


class InvitationResponseRejected(BusinessRuleViolation):
    """A resposta ao convite foi rejeitada por uma regra de negócio."""

    code = "invitation_response_rejected"
    http_status = HTTPStatus.CONFLICT


class InvitationNotFound(InvitationResponseRejected):
    """Convite inexistente ou inacessível ao estudante."""

    code = "not_found"
    http_status = HTTPStatus.NOT_FOUND


class InvitationNotPending(InvitationResponseRejected):
    """O convite já foi respondido ou não está mais pendente."""

    code = "invitation_not_pending"


class InvitationFormationClosed(InvitationResponseRejected):
    code = "formation_closed"


class InvitationStudentAlreadyInTeam(InvitationResponseRejected):
    code = "student_already_in_team"


class InvitationTeamFull(InvitationResponseRejected):
    code = "team_full"


@transaction.atomic
def respond_invitation(
    *,
    actor: User,
    invitation_id: int,
    status: InvitationStatus,
) -> Invitation:
    """Aceita ou recusa um convite recebido pelo estudante."""
    if actor.role != UserRole.STUDENT:
        raise InvitationResponseRejected("Somente alunos podem responder convites.")

    student = Student.objects.select_related("user").filter(user=actor).first()

    if student is None:
        raise InvitationResponseRejected("O perfil de aluno não foi encontrado.")

    if not actor.is_active or not actor.email_confirmed:
        raise InvitationResponseRejected(
            "O estudante não possui cadastro ativo e confirmado."
        )

    invitation_ref = (
        Invitation.objects.filter(pk=invitation_id).values("team_id").first()
    )

    if invitation_ref is None:
        raise InvitationNotFound("Convite não encontrado.")

    team = Team.objects.select_for_update().filter(pk=invitation_ref["team_id"]).first()

    if team is None:
        raise InvitationNotFound("Equipe não encontrada.")

    invitation = (
        Invitation.objects.select_for_update()
        .select_related("team", "student", "team__edition")
        .filter(pk=invitation_id, team_id=team.pk)
        .first()
    )

    if invitation is None:
        raise InvitationNotFound("Convite não encontrado.")

    if invitation.student_id != student.pk:
        raise InvitationNotFound("Este convite não pertence ao estudante autenticado.")

    if invitation.status != InvitationStatus.PENDING:
        raise InvitationNotPending("Este convite não está mais pendente.")

    now = timezone.now()

    formation_open = is_formation_open_for_team(invitation.team, now)

    if not formation_open:
        raise InvitationFormationClosed(
            "Não existe prazo de formação aberto para esta equipe."
        )

    if invitation.team.status != TeamStatus.ACTIVE:
        raise InvitationResponseRejected(
            "Não é possível responder a convites de equipes desclassificadas."
        )

    if status == InvitationStatus.DECLINED:
        invitation.status = InvitationStatus.DECLINED
        invitation.responded_at = now
        invitation.save(update_fields=["status", "responded_at", "updated_at"])

        leader_membership = (
            TeamMember.objects.filter(
                team=invitation.team,
                role=MemberRole.LEADER,
                active=True,
            )
            .select_related("student__user")
            .first()
        )

        if leader_membership:
            create_notification(
                user=leader_membership.student.user,
                notification_type=NotificationType.TEAM,
                title="Convite recusado",
                message=(
                    f"{student.user.name} recusou o convite "
                    f"para participar da equipe {invitation.team.name}."
                ),
                link=f"/equipes/{invitation.team.id}",
            )

        return invitation

    already_in_team = TeamMember.objects.filter(
        edition=invitation.team.edition,
        student=student,
        active=True,
    ).exists()

    if already_in_team:
        raise InvitationStudentAlreadyInTeam(
            "O estudante já participa de uma equipe ativa nesta edição."
        )

    current_members = TeamMember.objects.filter(
        team=invitation.team,
        active=True,
    ).count()

    if current_members >= invitation.team.edition.max_members:
        raise InvitationTeamFull("A equipe já atingiu o limite máximo de integrantes.")

    try:
        with transaction.atomic():
            TeamMember.objects.create(
                team=invitation.team,
                edition=invitation.team.edition,
                student=student,
                role=MemberRole.MEMBER,
            )
    except IntegrityError as error:
        raise InvitationResponseRejected(
            "Não foi possível aceitar o convite. "
            "O estudante pode já estar vinculado a outra equipe."
        ) from error

    invitation.status = InvitationStatus.ACCEPTED
    invitation.responded_at = now
    invitation.save(update_fields=["status", "responded_at", "updated_at"])

    Invitation.objects.filter(
        student=student,
        team__edition=invitation.team.edition,
        status=InvitationStatus.PENDING,
    ).exclude(pk=invitation.pk).update(
        status=InvitationStatus.CANCELLED,
        updated_at=now,
    )

    JoinRequest.objects.filter(
        student=student,
        team__edition=invitation.team.edition,
        status=RequestStatus.PENDING,
    ).exclude(team_id=invitation.team_id).update(
        status=RequestStatus.CANCELLED,
        updated_at=now,
    )

    leader_membership = (
        TeamMember.objects.filter(
            team=invitation.team,
            role=MemberRole.LEADER,
            active=True,
        )
        .select_related("student__user")
        .first()
    )

    if leader_membership:
        create_notification(
            user=leader_membership.student.user,
            notification_type=NotificationType.TEAM,
            title="Convite aceito",
            message=(
                f"{student.user.name} aceitou o convite "
                f"para participar da equipe {invitation.team.name}."
            ),
            link=f"/equipes/{invitation.team.id}",
        )

    return invitation
