from http import HTTPStatus

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.core.exceptions import AppError, BusinessRuleViolation
from apps.editions.enums import EditionStatus
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.teams.enums import TeamStatus
from apps.teams.models import Team


class TeamNotFound(AppError):
    """A equipe informada não foi encontrada."""

    code = "not_found"
    http_status = HTTPStatus.NOT_FOUND


class TeamAlreadyDisqualified(BusinessRuleViolation):
    """A equipe já está desclassificada."""

    code = "team_already_disqualified"


class EditionClosed(BusinessRuleViolation):
    """A edição está encerrada."""

    code = "edition_closed"


@transaction.atomic
def disqualify_team(*, actor: User, team_id: int, reason: str) -> Team:
    """Desclassifica uma equipe e seu projeto, quando existir.

    Registra a justificativa e o administrador responsável.
    """
    ensure_actor_is_admin(actor)

    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise TeamNotFound("Equipe não encontrada.")

    if team.status == TeamStatus.DISQUALIFIED:
        raise TeamAlreadyDisqualified("A equipe já está desclassificada.")

    if team.edition.status == EditionStatus.CLOSED:
        raise EditionClosed("A edição está encerrada e não pode ser alterada.")

    if team.edition.status != EditionStatus.PUBLISHED:
        raise ValidationError("A equipe não pertence à edição vigente.")

    if team.status != TeamStatus.ACTIVE:
        raise ValidationError(
            "Não é possível desclassificar uma equipe que não está ativa."
        )

    if not reason or not reason.strip():
        raise ValidationError("A justificativa da desclassificação é obrigatória.")

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

    project = Project.objects.filter(team=team).first()
    if project is not None:
        project.status = ProjectStatus.DISQUALIFIED
        project.save(update_fields=["status", "updated_at"])

    return team
