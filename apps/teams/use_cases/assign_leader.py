"""Trocar o líder pelo administrador (líder ausente ou equipe abandonada)."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.rules import ensure_edition_not_closed
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.teams.enums import MemberRole, RequestStatus, TeamStatus
from apps.teams.exceptions import InvalidNewLeader, TeamNotActive
from apps.teams.models import LeadershipRequest, Team, TeamMember


@transaction.atomic
def assign_leader(*, actor: User, member: TeamMember) -> Team:
    """Faz do integrante ativo `member` o líder; o líder atual vira integrante.

    O pedido de liderança pendente da equipe é cancelado: a coordenação já
    decidiu, e o pedido ficaria parado sem professor para responder.

    Sem rota no contrato: ação do Django admin. Levanta NotAdminActor,
    TeamNotActive, EditionClosed e InvalidNewLeader.
    """
    ensure_actor_is_admin(actor)
    team = (
        Team.objects.select_for_update()
        .select_related("edition")
        .get(pk=member.team_id)
    )
    if team.status != TeamStatus.ACTIVE:
        raise TeamNotActive()
    ensure_edition_not_closed(team.edition)
    member = TeamMember.objects.select_for_update().get(pk=member.pk)
    if not member.active or member.role == MemberRole.LEADER:
        raise InvalidNewLeader()
    # Rebaixa antes de promover: a constraint aceita um só líder ativo.
    team.members.filter(active=True, role=MemberRole.LEADER).update(
        role=MemberRole.MEMBER, updated_at=timezone.now()
    )
    member.role = MemberRole.LEADER
    member.save(update_fields=["role", "updated_at"])
    now = timezone.now()
    LeadershipRequest.objects.filter(team=team, status=RequestStatus.PENDING).update(
        status=RequestStatus.CANCELLED,
        decision_justification="Liderança definida pela coordenação.",
        decided_at=now,
        updated_at=now,
    )
    for active in team.members.filter(active=True).select_related("student__user"):
        create_notification(
            user=active.student.user,
            notification_type=NotificationType.TEAM,
            title="Liderança da equipe alterada",
            message=f"A coordenação definiu {member.student.user.name} como líder "
            f"da equipe {team.name}.",
            link=f"/equipes/{team.id}",
        )
    return team
