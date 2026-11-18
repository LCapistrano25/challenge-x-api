from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.editions.enums import FieldKind, StageKind
from apps.projects.exceptions import (
    CategoryNotAvailable,
    ChallengeNotEligible,
    ChallengeNotSelected,
    FormationClosed,
    NotTeamLeader,
    ProjectAccessDenied,
    ProjectNotFound,
    ProjectTitleTaken,
    StageDeadlineClosed,
    StageNotFound,
    StageNotOpen,
    TeamDisqualified,
    TeamIncomplete,
)
from apps.teams.enums import TeamSituation, TeamStatus

# Os models importam estas regras; por isso as que consultam outro app pegam os
# models pelo registro do Django, sem import que fecharia o ciclo.


def ensure_project_in_team_edition(project) -> None:
    """Equipe, desafio e categoria do projeto são todos da mesma edição (RN01)."""
    edition_id = project.edition_id
    if project.team.edition_id != edition_id:
        raise ValidationError({"edition": "A edição não é a da equipe."})
    if project.challenge_id and project.challenge.edition_id != edition_id:
        raise ValidationError({"challenge": "O desafio é de outra edição."})
    if project.category_id and project.category.edition_id != edition_id:
        raise ValidationError({"category": "A categoria é de outra edição."})


def ensure_project_complete(project) -> None:
    """Só entrega projeto com desafio, título e resumo (RF30, RF31, RF51)."""
    filled = {
        "challenge": project.challenge_id,
        "title": project.title,
        "summary": project.summary,
    }
    missing = {
        f: "Obrigatório para enviar a entrega." for f, v in filled.items() if not v
    }
    if missing:
        raise ValidationError(missing)


def ensure_item_matches_field(item) -> None:
    """O item responde a um campo da etapa da entrega, com o mesmo tipo (RF31)."""
    if item.field.stage_id != item.version.submission.stage_id:
        raise ValidationError({"field": "O campo é de outra etapa."})
    if item.field.kind != item.kind:
        raise ValidationError({"kind": "O tipo do item não é o tipo do campo."})


def ensure_stage_in_project_edition(record) -> None:
    """Entrega ou prorrogação só de etapa da edição do projeto (RF14, RF31)."""
    if record.stage.edition_id != record.project.edition_id:
        raise ValidationError({"stage": "A etapa é de outra edição."})


def ensure_extension_after_stage_end(extension) -> None:
    """A prorrogação só estende o prazo da etapa, nunca encurta (RF14)."""
    if extension.ends_at <= extension.stage.ends_at:
        raise ValidationError(
            {"ends_at": "O novo prazo precisa ser depois do fim da etapa."}
        )


def ensure_actor_is_team_leader(team, actor) -> None:
    """Exige que quem age seja o líder ativo da equipe (RF29, RF30)."""
    members = apps.get_model("teams", "TeamMember").objects
    is_leader = (
        actor is not None
        and members.filter(
            team=team, student_id=actor.pk, role="LEADER", active=True
        ).exists()
    )
    if not is_leader:
        raise NotTeamLeader()


def ensure_formation_period_is_open(edition) -> None:
    """Exige prazo de formação aberto; sem etapa de formação, está fechado (RF29)."""
    now = timezone.now()
    stages = apps.get_model("editions", "Stage").objects
    if not stages.filter(
        edition=edition, kind=StageKind.FORMATION, starts_at__lte=now, ends_at__gte=now
    ).exists():
        raise FormationClosed()


def ensure_challenge_eligible(team, challenge) -> None:
    """O desafio é ativo, da edição e de curso de integrante ativo da equipe (RF29)."""
    # Import aqui: selectors importa os models de projects, que importam este módulo.
    from apps.projects.selectors import get_eligible_challenges

    if not get_eligible_challenges(team).filter(pk=challenge.pk).exists():
        raise ChallengeNotEligible()


def ensure_project_has_challenge(project) -> None:
    """Os dados do projeto só se cadastram depois de escolhido o desafio (RF30)."""
    if not project.challenge_id:
        raise ChallengeNotSelected()


def ensure_team_has_project(team) -> None:
    """A categoria só se escolhe com o projeto já criado, junto do desafio (RF30)."""
    projects = apps.get_model("projects", "Project").objects
    if not projects.filter(team=team).exists():
        raise ProjectNotFound()


def ensure_category_available(team, category) -> None:
    """A categoria é ativa e da edição da equipe (RF30, RF49)."""
    if category.edition_id != team.edition_id or not category.active:
        raise CategoryNotAvailable()


def ensure_project_title_is_free(project, title: str) -> None:
    """Impede título igual ao de outro projeto da edição, sem olhar caixa (RN03).

    O banco recusa o mesmo caso (unique_project_title_per_edition); aqui sai o
    erro de negócio em vez de IntegrityError. Título em branco não conta.
    """
    projects = apps.get_model("projects", "Project").objects
    taken = projects.filter(edition_id=project.edition_id, title__iexact=title)
    if title and taken.exclude(pk=project.pk).exists():
        raise ProjectTitleTaken()


def ensure_actor_is_team_member(team, actor) -> None:
    """Exige que quem consulta seja integrante ativo da equipe (RF29)."""
    members = apps.get_model("teams", "TeamMember").objects
    if not members.filter(team=team, student_id=actor.pk, active=True).exists():
        raise ProjectAccessDenied()


def ensure_actor_can_view_project(team, actor) -> None:
    """Aluno integrante ativo, professor do curso do desafio ou admin (RF30, RF20)."""
    if actor.role == UserRole.ADMIN:
        return
    if actor.role == UserRole.STUDENT:
        ensure_actor_is_team_member(team, actor)
        return
    project = apps.get_model("projects", "Project").objects.filter(team=team).first()
    links = apps.get_model("accounts", "TeacherCourse").objects
    is_course_teacher = (
        actor.role == UserRole.TEACHER
        and project is not None
        and project.challenge_id is not None
        and links.filter(
            teacher_id=actor.pk, course_id=project.challenge.course_id, active=True
        ).exists()
    )
    if not is_course_teacher:
        raise ProjectAccessDenied()


def ensure_team_not_disqualified(team) -> None:
    """Equipe desclassificada não envia entrega (RF31)."""
    if team.status == TeamStatus.DISQUALIFIED:
        raise TeamDisqualified()


def ensure_team_not_incomplete(team) -> None:
    """Equipe incompleta não envia entrega; sem situação apurada, pode (RF31, RF51)."""
    blocked = {TeamSituation.INCOMPLETE, TeamSituation.REQUIREMENTS_NOT_MET}
    if team.situation in blocked:
        raise TeamIncomplete()


def ensure_stage_accepts_delivery(project, stage) -> None:
    """A etapa é de entrega e da edição do projeto (RF31)."""
    if stage.kind != StageKind.SUBMISSION or stage.edition_id != project.edition_id:
        raise StageNotFound()


def ensure_stage_deadline_open(project, stage) -> None:
    """Só entrega do início da etapa até o prazo da equipe, com prorrogação (RF31)."""
    # Import aqui: selectors importa os models de projects, que importam este módulo.
    from apps.projects.selectors import get_submission_deadline

    now = timezone.now()
    if now < stage.starts_at:
        raise StageNotOpen()
    if now > get_submission_deadline(project, stage):
        raise StageDeadlineClosed()


def ensure_items_match_stage_fields(stage, items: list[dict]) -> None:
    """Cada item responde a um campo LINK da etapa, sem repetir, e os obrigatórios
    são respondidos (RF31). Arquivos ficam para a V5.

    `items` é uma lista de {"field": StageSubmissionField, "link": str}.
    """
    if not items:
        raise ValidationError({"items": "Informe ao menos um item."})

    fields = [item["field"] for item in items]
    if any(f.stage_id != stage.pk for f in fields):
        raise ValidationError({"items": "O campo é de outra etapa."})
    if any(f.kind != FieldKind.LINK for f in fields):
        raise ValidationError({"items": "Nesta versão só há envio de links."})
    if len({f.pk for f in fields}) != len(fields):
        raise ValidationError({"items": "O campo foi enviado mais de uma vez."})

    required = stage.submission_fields.filter(kind=FieldKind.LINK, required=True)
    missing = required.exclude(pk__in=[f.pk for f in fields])
    if missing.exists():
        raise ValidationError({"items": "Preencha todos os campos obrigatórios."})
