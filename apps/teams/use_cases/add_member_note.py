
from django.db import transaction

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.editions.models import Stage
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.models import MemberNote, Team, TeamMember


class AddMemberNoteRejected(Exception):
    """O registro da observação foi rejeitado por uma regra de negócio."""


@transaction.atomic
def add_member_note(
    *,
    actor: User,
    team_id: int,
    member_id: int,
    stage_id: int,
    text: str,
) -> MemberNote:
    """Registra uma observação confidencial sobre outro integrante da equipe."""
    if actor.role != UserRole.STUDENT:
        raise AddMemberNoteRejected("Somente acadêmicos podem registrar observações.")

    author = Student.objects.filter(user=actor).first()

    if author is None:
        raise AddMemberNoteRejected("O perfil de acadêmico não foi encontrado.")

    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise AddMemberNoteRejected("Equipe não encontrada.")

    if team.status != TeamStatus.ACTIVE:
        raise AddMemberNoteRejected(
            "Não é possível registrar observações em uma equipe inativa."
        )

    leader_membership = TeamMember.objects.filter(
        team=team,
        student=author,
        role=MemberRole.LEADER,
        active=True,
    ).exists()

    if not leader_membership:
        raise AddMemberNoteRejected(
            "Somente o líder ativo da equipe pode registrar observações."
        )

    member = TeamMember.objects.filter(
        pk=member_id,
        team=team,
        active=True,
    ).first()

    if member is None:
        raise AddMemberNoteRejected(
            "O vínculo informado não é de um integrante ativo desta equipe."
        )

    if member.student_id == author.pk:
        raise AddMemberNoteRejected(
            "O líder não pode registrar observações sobre si mesmo."
        )

    if not text or not text.strip():
        raise AddMemberNoteRejected("O texto da observação é obrigatório.")

    stage = Stage.objects.filter(pk=stage_id).first()

    if stage is None:
        raise AddMemberNoteRejected("Etapa não encontrada.")

    if stage.edition_id != team.edition_id:
        raise AddMemberNoteRejected(
            "A etapa informada não pertence à edição da equipe."
        )

    return MemberNote.objects.create(
        member=member,
        author=author,
        stage=stage,
        text=text.strip(),
    )
