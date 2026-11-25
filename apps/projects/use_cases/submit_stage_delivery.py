"""UC34 — Enviar a entrega da etapa (links, arquivos, canvas, SWOT). RF31. RN01."""

from django.db import transaction
from django.db.models import Max

from apps.accounts.models import User
from apps.editions.enums import FieldKind
from apps.editions.models import Stage
from apps.editions.rules import ensure_edition_not_closed
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.projects.files import (
    build_storage_key,
    clean_file_name,
    delete_delivery_file,
    get_extension,
    save_delivery_file,
)
from apps.projects.models import (
    Project,
    Submission,
    SubmissionItem,
    SubmissionReceipt,
    SubmissionVersion,
)
from apps.projects.rules import (
    ensure_actor_is_team_leader,
    ensure_file_matches_field,
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
    """Registra uma nova versão da entrega da etapa, com um item por campo.

    `items` é uma lista de {"field": StageSubmissionField, "link": str} para campo
    LINK, {"field": StageSubmissionField, "file": UploadedFile} para campo FILE ou
    {"field": StageSubmissionField, "content": dict} para campo CANVAS ou SWOT.
    Cada envio cria a versão seguinte e o comprovante; nenhuma versão anterior muda,
    e arquivo de versão anterior nunca é apagado nem trocado.

    Nada é gravado antes de todas as regras passarem. Se a gravação falhar depois
    de algum arquivo já estar no armazenamento, os arquivos desta tentativa são
    apagados e a transação desfaz as linhas.

    Levanta NotTeamLeader se o actor não for o líder ativo, EditionClosed,
    TeamDisqualified, TeamIncomplete, StageNotFound, StageNotOpen e
    StageDeadlineClosed pelas regras da entrega, FileFormatNotAllowed e
    FileTooLarge pelas regras do arquivo, StorageUnavailable se o armazenamento
    falhar e ValidationError se o projeto estiver incompleto ou os itens não
    baterem com os campos da etapa.
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
    for item in items:
        if "file" in item:
            ensure_file_matches_field(item["field"], item["file"])

    # Chaves já gravadas no armazenamento nesta tentativa, para limpar se falhar.
    stored_keys: list[str] = []
    try:
        submission, _ = Submission.objects.get_or_create(project=project, stage=stage)
        last = submission.versions.aggregate(last=Max("number"))["last"] or 0
        version = SubmissionVersion.objects.create(
            submission=submission,
            number=last + 1,
            submitted_by=actor.student,
            notes=notes,
        )
        for item in items:
            if "file" in item:
                _create_file_item(version, item, project, stage, stored_keys)
            elif "content" in item:
                SubmissionItem.objects.create(
                    version=version,
                    field=item["field"],
                    kind=item["field"].kind,
                    content=item["content"],
                )
            else:
                SubmissionItem.objects.create(
                    version=version,
                    field=item["field"],
                    kind=FieldKind.LINK,
                    link=item["link"],
                )
        SubmissionReceipt.objects.create(version=version)
    except BaseException:
        for key in stored_keys:
            delete_delivery_file(key)
        raise
    _notify_stage_delivery(team=team, project=project, stage=stage, version=version)
    return version


def _create_file_item(version, item, project, stage, stored_keys) -> SubmissionItem:
    upload = item["file"]
    key = build_storage_key(project, stage, version.number, get_extension(upload.name))
    size = save_delivery_file(file=upload, key=key)
    stored_keys.append(key)
    return SubmissionItem.objects.create(
        version=version,
        field=item["field"],
        kind=FieldKind.FILE,
        file_url=key,
        file_name=clean_file_name(upload.name),
        size_bytes=size,
    )


def _notify_stage_delivery(*, team, project, stage, version) -> None:
    members = team.members.filter(active=True).select_related("student__user")
    for member in members:
        create_notification(
            user=member.student.user,
            notification_type=NotificationType.DELIVERABLE,
            title=f"Entrega registrada — {stage.name}",
            message=(
                f"A versão {version.number} da etapa {stage.name} "
                f"do projeto {project.title} foi enviada."
            ),
            link=f"/projects/{project.id}/deliverables",
        )
