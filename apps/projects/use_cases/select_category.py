"""UC39 — Escolher a categoria do projeto. RF30, RF49. Regras: RN01."""

from django.db import transaction

from apps.accounts.models import User
from apps.editions.models import Category
from apps.projects.models import Project
from apps.projects.rules import (
    ensure_actor_is_team_leader,
    ensure_category_available,
    ensure_formation_period_is_open,
    ensure_team_has_project,
)
from apps.teams.models import Team


@transaction.atomic
def select_category(*, actor: User, team: Team, category: Category) -> Project:
    """Grava a categoria escolhida pela equipe; pode trocar até o fim da formação.

    Não mexe em desafio, título, resumo nem objetivo, e a categoria não se limpa.

    Levanta NotTeamLeader se o actor não for o líder ativo, FormationClosed fora
    do prazo de formação, ProjectNotFound se a equipe ainda não tem projeto e
    CategoryNotAvailable se a categoria não for ativa e da edição da equipe.
    """
    # Trava a equipe: duas escolhas ao mesmo tempo viram uma depois da outra.
    team = Team.objects.select_for_update().select_related("edition").get(pk=team.pk)

    ensure_actor_is_team_leader(team, actor)
    ensure_formation_period_is_open(team.edition)
    ensure_team_has_project(team)
    ensure_category_available(team, category)

    project = Project.objects.get(team=team)
    project.category = category
    project.save(update_fields=["category", "updated_at"])
    return project
