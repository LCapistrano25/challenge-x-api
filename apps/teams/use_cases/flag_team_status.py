from django.db import transaction
from django.utils import timezone

from apps.editions.enums import StageKind
from apps.editions.models import Stage
from apps.teams.enums import TeamSituation, TeamStatus
from apps.teams.models import Team
from apps.teams.rules import compute_unmet_requirements, is_formation_open_for_team


class FlagTeamStatusRejected(Exception):
    """A identificação da situação da equipe foi rejeitada."""


@transaction.atomic
def flag_team_status(*, team_id: int) -> Team:
    """Identifica e registra a situação da equipe após o fim da formação."""
    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise FlagTeamStatusRejected("Equipe não encontrada.")

    if team.status != TeamStatus.ACTIVE:
        raise FlagTeamStatusRejected("Apenas equipes ativas podem ser classificadas.")

    # A situação é congelada após a primeira classificação.
    if team.situation is not None:
        return team

    formation_stage = Stage.objects.filter(
        edition=team.edition,
        kind=StageKind.FORMATION,
    ).first()

    if formation_stage is None:
        raise FlagTeamStatusRejected(
            "Não existe etapa de formação para a edição da equipe."
        )

    now = timezone.now()

    if now < formation_stage.starts_at:
        raise FlagTeamStatusRejected("O período de formação ainda não começou.")

    if is_formation_open_for_team(team, now):
        raise FlagTeamStatusRejected(
            "O período de formação ou a extensão ainda está aberto."
        )

    unmet = compute_unmet_requirements(team)

    team.situation = TeamSituation.INCOMPLETE if unmet else TeamSituation.COMPLETE
    team.save(update_fields=["situation", "updated_at"])

    return team
