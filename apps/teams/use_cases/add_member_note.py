from django.db import transaction

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.exceptions import (
    MemberNoteNotFound,
    MemberNotePermissionDenied,
    MemberNoteRejected,
)
from apps.teams.models import MemberNote, Team, TeamMember


@transaction.atomic
def add_member_note(
    *,
    actor: User,
    team_id: int,
    member_id: int,
    text: str,
) -> MemberNote:
    """Registra uma observação confidencial sobre outro integrante da equipe."""
    if actor.role != UserRole.STUDENT:
        raise MemberNotePermissionDenied(
            "Somente acadêmicos podem registrar observações."
        )

    author = Student.objects.filter(user=actor).first()

    if author is None:
        raise MemberNoteRejected("O perfil de acadêmico não foi encontrado.")

    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise MemberNoteNotFound("Equipe não encontrada.")

    if team.status != TeamStatus.ACTIVE:
        raise MemberNoteRejected(
            "Não é possível registrar observações em uma equipe inativa."
        )

    leader_membership = TeamMember.objects.filter(
        team=team,
        student=author,
        role=MemberRole.LEADER,
        active=True,
    ).exists()

    if not leader_membership:
        raise MemberNotePermissionDenied(
            "Somente o líder ativo da equipe pode registrar observações."
        )

    member = TeamMember.objects.filter(
        pk=member_id,
        team=team,
        active=True,
    ).first()

    if member is None:
        raise MemberNoteNotFound(
            "O vínculo informado não é de um integrante ativo desta equipe."
        )

    if member.student_id == author.pk:
        raise MemberNoteRejected(
            "O líder não pode registrar observações sobre si mesmo."
        )

    if not text or not text.strip():
        raise MemberNoteRejected("O texto da observação é obrigatório.")

    return MemberNote.objects.create(
        member=member,
        author=author,
        text=text.strip(),
    )
