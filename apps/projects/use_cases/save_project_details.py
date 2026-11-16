"""UC33 — Cadastrar os dados do projeto. RF30. Regras: RN03."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.projects.exceptions import ChallengeNotSelected, ProjectTitleTaken
from apps.projects.models import Project
from apps.projects.rules import (
    ensure_actor_is_team_leader,
    ensure_formation_period_is_open,
    ensure_project_has_challenge,
    ensure_project_title_is_free,
)
from apps.teams.models import Team


@transaction.atomic
def save_project_details(
    *,
    actor: User,
    team: Team,
    title: str,
    summary: str,
    objective: str = "",
) -> Project:
    """Grava título, resumo e objetivo; serve para cadastrar e para atualizar.

    Não mexe no desafio nem na categoria. O título sai sem espaços extras.

    Levanta NotTeamLeader se o actor não for o líder ativo, FormationClosed fora
    do prazo de formação, ChallengeNotSelected se a equipe ainda não escolheu o
    desafio, ValidationError se título ou resumo ficarem em branco e
    ProjectTitleTaken se outro projeto da edição já tem o título.
    """
    # Trava a equipe: duas gravações ao mesmo tempo viram uma depois da outra.
    team = Team.objects.select_for_update().select_related("edition").get(pk=team.pk)

    ensure_actor_is_team_leader(team, actor)
    ensure_formation_period_is_open(team.edition)

    project = Project.objects.filter(team=team).first()
    if project is None:
        raise ChallengeNotSelected()
    ensure_project_has_challenge(project)

    title = " ".join(title.split())
    summary = summary.strip()
    blank = {
        field: "Este campo não pode ficar em branco."
        for field, value in (("title", title), ("summary", summary))
        if not value
    }
    if blank:
        raise ValidationError(blank)
    ensure_project_title_is_free(project, title)

    project.title = title
    project.summary = summary
    project.objective = objective.strip()
    try:
        # Savepoint próprio: o IntegrityError não deixa a transação inutilizável.
        with transaction.atomic():
            project.save(update_fields=["title", "summary", "objective", "updated_at"])
    except IntegrityError:
        # Duas requisições passam pela checagem acima; o banco desempata.
        if (
            Project.objects.filter(edition=project.edition, title__iexact=title)
            .exclude(pk=project.pk)
            .exists()
        ):
            raise ProjectTitleTaken() from None
        raise
    return project
