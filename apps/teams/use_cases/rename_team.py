"""RF21, Art. 15 § 1º — Editar o nome da equipe durante a formação (#233)."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.projects.rules import (
    ensure_actor_is_team_leader,
    ensure_formation_period_is_open,
    ensure_team_not_disqualified,
)
from apps.teams.enums import TeamStatus
from apps.teams.exceptions import TeamNameTaken
from apps.teams.models import Team
from apps.teams.use_cases.disqualify_team import TeamNotFound


@transaction.atomic
def rename_team(*, actor: User, team_id: int, name: str) -> Team:
    """Troca o nome da equipe; só o líder ativo, com a formação aberta.

    Levanta TeamNotFound, NotTeamLeader, TeamDisqualified, FormationClosed,
    TeamNameTaken e ValidationError (nome vazio).
    """
    team = Team.objects.select_for_update().filter(pk=team_id).first()
    if team is None:
        raise TeamNotFound("Equipe não encontrada.")
    ensure_actor_is_team_leader(team, actor)
    ensure_team_not_disqualified(team)
    ensure_formation_period_is_open(team.edition)

    name = name.strip()
    if not name:
        raise ValidationError({"name": "O nome da equipe é obrigatório."})
    taken = (
        Team.objects.filter(edition=team.edition, name=name)
        .exclude(pk=team.pk)
        .exclude(status=TeamStatus.DISBANDED)
        .exists()
    )
    if taken:
        raise TeamNameTaken()

    team.name = name
    team.save(update_fields=["name", "updated_at"])
    return team
