"""UC34 — Enviar a entrega da etapa com links. RF31. Regras: RN01."""

from django.db import transaction
from django.db.models import Max

from apps.accounts.models import User
from apps.editions.models import Stage
from apps.editions.rules import ensure_edition_not_closed
from apps.projects.models import (
    Project,
    Submission,
    SubmissionItem,
    SubmissionReceipt,
    SubmissionVersion,
)
from apps.projects.rules import (
    ensure_actor_is_team_leader,
    ensure_items_match_stage_fields,
    ensure_project_complete,
    ensure_stage_accepts_delivery,
    ensure_stage_deadline_open,
    ensure_team_not_disqualified,
    ensure_team_not_incomplete,
)
from apps.teams.models import Team


@transaction.atomic
def submit_stage_delivery(
    *,
    actor: User,
    project: Project,
    stage: Stage,
    items: list[dict],
    notes: str = "",
) -> SubmissionVersion:
    """Registra uma nova versão da entrega da etapa, com um link por campo.

    `items` é uma lista de {"field": StageSubmissionField, "link": str}. Cada
    envio cria a versão seguinte e o comprovante; nenhuma versão anterior muda.
    Arquivos ficam para a V5.

    Levanta NotTeamLeader se o actor não for o líder ativo, EditionClosed,
    TeamDisqualified, TeamIncomplete, StageNotFound, StageNotOpen e
    StageDeadlineClosed pelas regras da entrega, e ValidationError se o projeto
    estiver incompleto ou os itens não baterem com os campos da etapa.
    """
    # Trava a equipe: dois envios ao mesmo tempo viram um depois do outro.
    team = (
        Team.objects.select_for_update()
        .select_related("edition")
        .get(pk=project.team_id)
    )
    # Relê o projeto já com a trava: título e resumo podem ter mudado.
    project = Project.objects.get(pk=project.pk)

    ensure_actor_is_team_leader(team, actor)
    ensure_edition_not_closed(team.edition)
    ensure_team_not_disqualified(team)
    ensure_team_not_incomplete(team)
    ensure_project_complete(project)
    ensure_stage_accepts_delivery(project, stage)
    ensure_stage_deadline_open(project, stage)
    ensure_items_match_stage_fields(stage, items)

    submission, _ = Submission.objects.get_or_create(project=project, stage=stage)
    last = submission.versions.aggregate(last=Max("number"))["last"] or 0
    version = SubmissionVersion.objects.create(
        submission=submission,
        number=last + 1,
        submitted_by=actor.student,
        notes=notes,
    )
    for item in items:
        SubmissionItem.objects.create(
            version=version,
            field=item["field"],
            kind=item["field"].kind,
            link=item["link"],
        )
    SubmissionReceipt.objects.create(version=version)
    return version
