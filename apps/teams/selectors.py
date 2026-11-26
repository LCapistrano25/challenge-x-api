from django.db.models import QuerySet

from apps.accounts.enums import UserRole
from apps.accounts.models import Student
from apps.teams.enums import InvitationStatus
from apps.teams.models import Invitation, TeamMember


def list_invitable_students(*, team, search: str) -> QuerySet[Student]:
    """Alunos que a equipe pode convidar, por parte do nome (RF22, #232).

    Mesmas regras do convite (invite_member): aluno ativo, com e-mail confirmado
    e sem equipe ativa na edição; sai também quem já tem convite pendente desta
    equipe. Sem restrição por curso.
    """
    return (
        Student.objects.filter(
            user__role=UserRole.STUDENT,
            user__is_active=True,
            user__email_confirmed=True,
            user__name__icontains=search,
        )
        # Subconsultas: exclude com duas condições numa relação de muitos não
        # exige que as duas valham para o mesmo vínculo.
        .exclude(
            pk__in=TeamMember.objects.filter(edition=team.edition, active=True).values(
                "student_id"
            )
        )
        .exclude(
            pk__in=Invitation.objects.filter(
                team=team, status=InvitationStatus.PENDING
            ).values("student_id")
        )
        .select_related("user", "course")
        .order_by("user__name", "pk")
    )
