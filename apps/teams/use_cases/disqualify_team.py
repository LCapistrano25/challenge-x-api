from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.enums import EditionStatus
from apps.teams.enums import TeamStatus
from apps.teams.models import Team


class DisqualifyTeamRejected(Exception):
    """A desclassificação foi rejeitada por uma regra de negócio."""


class TeamNotFound(DisqualifyTeamRejected):
    """A equipe informada não foi encontrada."""


@transaction.atomic
def disqualify_team(*, actor: User, team_id: int, reason: str) -> Team:
    """Desclassifica uma equipe da edição vigente.

    Registra a justificativa e o administrador responsável.
    """
    ensure_actor_is_admin(actor)

    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise TeamNotFound("Equipe não encontrada.")

    if team.edition.status != EditionStatus.PUBLISHED:
        raise DisqualifyTeamRejected("A equipe não pertence à edição vigente.")

    if team.status != TeamStatus.ACTIVE:
        raise DisqualifyTeamRejected(
            "Não é possível desclassificar uma equipe que não está ativa."
        )

    if not reason or not reason.strip():
        raise DisqualifyTeamRejected(
            "A justificativa da desclassificação é obrigatória."
        )

    team.status = TeamStatus.DISQUALIFIED
    team.disqualification_reason = reason.strip()
    team.disqualified_at = timezone.now()
    team.disqualified_by = actor
    team.save(
        update_fields=[
            "status",
            "disqualification_reason",
            "disqualified_at",
            "disqualified_by",
            "updated_at",
        ]
    )

    return team
