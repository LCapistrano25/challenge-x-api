import secrets
import string
from http import HTTPStatus

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.editions.models import Edition
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.exceptions import TeamCreationRejected, TeamNameTaken
from apps.teams.models import Team, TeamMember
from apps.teams.rules import get_open_formation_stage
from apps.teams.use_cases.invite_member import invite_member


class TeamInvitationsRequired(TeamCreationRejected):
    """A equipe não nasce só com o líder: faltam convites para os demais."""

    code = "team_invitations_required"
    http_status = HTTPStatus.BAD_REQUEST


class NoCurrentEdition(TeamCreationRejected):
    code = "no_current_edition"
    http_status = HTTPStatus.CONFLICT


class FormationClosed(TeamCreationRejected):
    code = "formation_closed"
    http_status = HTTPStatus.CONFLICT


class StudentAlreadyInTeam(TeamCreationRejected):
    code = "student_already_in_team"
    http_status = HTTPStatus.CONFLICT


def _generate_team_code() -> str:
    """Gera um código de convite alfanumérico."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


@transaction.atomic
def create_team(
    *,
    actor: User,
    edition_id: int,
    name: str,
    invitations: list[dict] | None = None,
) -> Team:
    """Cria a equipe, faz do solicitante o líder ativo e convida os demais alunos.

    Cada convite é {"student_id": int} ou {"email": str}, como em invite_member. A
    equipe não pode nascer só com o líder: são exigidos ao menos min_members - 1
    convites (e nunca menos de 1) e no máximo max_members - 1. Qualquer convite
    recusado desfaz a criação inteira.
    """
    if actor.role != UserRole.STUDENT:
        raise TeamCreationRejected("Somente alunos podem criar equipes.")

    student = Student.objects.filter(user=actor).first()
    if student is None:
        raise TeamCreationRejected("O perfil de aluno não foi encontrado.")

    now = timezone.now()

    edition = Edition.objects.filter(pk=edition_id).first()
    if edition is None:
        raise NoCurrentEdition("Edição não encontrada.")

    formation_open = get_open_formation_stage(edition, now) is not None

    if not formation_open:
        raise FormationClosed("Não existe prazo de formação aberto para esta edição.")

    if TeamMember.objects.filter(
        edition=edition,
        student=student,
        active=True,
    ).exists():
        raise StudentAlreadyInTeam(
            "Você já participa de uma equipe ativa nesta edição."
        )

    name = name.strip()
    if not name:
        raise TeamCreationRejected("O nome da equipe é obrigatório.")

    if (
        Team.objects.filter(edition=edition, name=name)
        .exclude(status=TeamStatus.DISBANDED)
        .exists()
    ):
        raise TeamNameTaken("Já existe uma equipe com esse nome nesta edição.")

    invitations = invitations or []
    # O líder já é o primeiro integrante; o mínimo nunca deixa a equipe com 1 pessoa.
    needed = min(max(edition.min_members - 1, 1), edition.max_members - 1)
    if not needed <= len(invitations) <= edition.max_members - 1:
        raise TeamInvitationsRequired(
            f"Convide de {needed} a {edition.max_members - 1} alunos "
            "para criar a equipe."
        )

    for _ in range(5):
        code = _generate_team_code()
        if not Team.objects.filter(code=code).exists():
            break
    else:
        raise TeamCreationRejected("Não foi possível gerar um código de convite único.")

    try:
        with transaction.atomic():
            team = Team.objects.create(
                edition=edition,
                name=name,
                code=code,
            )
            TeamMember.objects.create(
                team=team,
                edition=edition,
                student=student,
                role=MemberRole.LEADER,
            )
    except IntegrityError as error:
        raise TeamCreationRejected(
            "Não foi possível criar a equipe. "
            "Verifique se o nome ou o vínculo já existe."
        ) from error

    for data in invitations:
        invite_member(actor=actor, team_id=team.pk, **data)

    return team
