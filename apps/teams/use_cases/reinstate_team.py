"""Reverter a desclassificação feita por engano. RF13 (correção pelo admin)."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.rules import ensure_edition_not_closed
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.teams.enums import TeamStatus
from apps.teams.exceptions import TeamNotDisqualified
from apps.teams.models import Team


@transaction.atomic
def reinstate_team(*, actor: User, team: Team) -> Team:
    """Volta a equipe a ACTIVE e o projeto a IN_PROGRESS, limpando o motivo.

    Sem rota no contrato: ação do Django admin. Resultados já calculados não
    incluem o projeto; o admin recalcula antes de homologar. Levanta
    NotAdminActor, TeamNotDisqualified e EditionClosed.
    """
    ensure_actor_is_admin(actor)
    team = Team.objects.select_for_update().select_related("edition").get(pk=team.pk)
    if team.status != TeamStatus.DISQUALIFIED:
        raise TeamNotDisqualified()
    ensure_edition_not_closed(team.edition)
    team.status = TeamStatus.ACTIVE
    team.disqualification_reason = ""
    team.disqualified_at = None
    team.disqualified_by = None
    team.save()
    project = Project.objects.filter(team=team).first()
    if project is not None:
        project.status = ProjectStatus.IN_PROGRESS
        project.save(update_fields=["status", "updated_at"])
    for member in team.members.filter(active=True).select_related("student__user"):
        create_notification(
            user=member.student.user,
            notification_type=NotificationType.TEAM,
            title="Desclassificação revertida",
            message=f"A equipe {team.name} voltou a participar do desafio.",
        )
    return team
