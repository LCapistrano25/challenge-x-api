"""UC32 — Escolher o desafio do projeto. RF29. Regras: RN01."""

from django.db import transaction

from apps.accounts.models import User
from apps.editions.models import Challenge
from apps.projects.models import Project
from apps.projects.rules import (
    ensure_actor_is_team_leader,
    ensure_challenge_eligible,
    ensure_formation_period_is_open,
)
from apps.teams.models import Team


@transaction.atomic
def select_challenge(*, actor: User, team: Team, challenge: Challenge) -> Project:
    """Grava o desafio escolhido pela equipe, criando o projeto se ainda não há.

    Trocar de desafio não mexe em título, resumo nem categoria.

    Levanta NotTeamLeader se o actor não for o líder ativo, FormationClosed fora
    do prazo de formação e ChallengeNotEligible se o desafio não for ativo, da
    edição e de curso de integrante ativo.
    """
    # Trava a equipe: duas escolhas ao mesmo tempo viram uma depois da outra.
    team = Team.objects.select_for_update().select_related("edition").get(pk=team.pk)

    ensure_actor_is_team_leader(team, actor)
    ensure_formation_period_is_open(team.edition)
    ensure_challenge_eligible(team, challenge)

    project, _ = Project.objects.get_or_create(
        team=team, defaults={"edition": team.edition}
    )
    project.challenge = challenge
    project.save(update_fields=["challenge", "updated_at"])
    return project
