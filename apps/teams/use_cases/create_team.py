
import secrets
import string

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.editions.enums import StageKind
from apps.editions.models import Edition, Stage
from apps.teams.enums import MemberRole
from apps.teams.models import Team, TeamMember


class TeamCreationRejected(Exception):
    """A equipe não pôde ser criada por uma regra de negócio."""


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
) -> Team:
    """Cria uma equipe e define o aluno solicitante como líder ativo."""
    if actor.role != UserRole.STUDENT:
        raise TeamCreationRejected("Somente alunos podem criar equipes.")

    student = Student.objects.filter(user=actor).first()
    if student is None:
        raise TeamCreationRejected("O perfil de aluno não foi encontrado.")

    now = timezone.now()

    edition = Edition.objects.filter(pk=edition_id).first()
    if edition is None:
        raise TeamCreationRejected("Edição não encontrada.")

    formation_open = Stage.objects.filter(
        edition=edition,
        kind=StageKind.FORMATION,
        starts_at__lte=now,
        ends_at__gte=now,
    ).exists()

    if not formation_open:
        raise TeamCreationRejected(
            "Não existe prazo de formação aberto para esta edição."
        )

    if TeamMember.objects.filter(
        edition=edition,
        student=student,
        active=True,
    ).exists():
        raise TeamCreationRejected(
            "Você já participa de uma equipe ativa nesta edição."
        )

    name = name.strip()
    if not name:
        raise TeamCreationRejected("O nome da equipe é obrigatório.")

    if Team.objects.filter(edition=edition, name=name).exists():
        raise TeamCreationRejected(
            "Já existe uma equipe com esse nome nesta edição."
        )

    for _ in range(5):
        code = _generate_team_code()
        if not Team.objects.filter(code=code).exists():
            break
    else:
        raise TeamCreationRejected(
            "Não foi possível gerar um código de convite único."
        )

    try:
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
            "Não foi possível criar a equipe. Verifique se o nome ou o vínculo já existe."
        ) from error

    return team
