
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.editions.enums import StageKind
from apps.editions.models import Stage
from apps.teams.enums import InvitationStatus, MemberRole, TeamStatus
from apps.teams.models import Invitation, Team, TeamMember


class InvitationRejected(Exception):
    """O convite não pôde ser enviado por uma regra de negócio."""


@transaction.atomic
def invite_member(
    *,
    actor: User,
    team_id: int,
    student_id: int,
) -> Invitation:
    """Envia um convite do líder para um estudante."""
    if actor.role != UserRole.STUDENT:
        raise InvitationRejected("Somente alunos podem enviar convites.")

    student_actor = Student.objects.filter(user=actor).first()
    if student_actor is None:
        raise InvitationRejected("O perfil de aluno não foi encontrado.")

    team = Team.objects.select_for_update().filter(pk=team_id).first()
    if team is None:
        raise InvitationRejected("Equipe não encontrada.")

    is_leader = TeamMember.objects.filter(
        team=team,
        student=student_actor,
        role=MemberRole.LEADER,
        active=True,
    ).exists()

    if not is_leader:
        raise InvitationRejected(
            "Somente o líder ativo da equipe pode enviar convites."
        )

    now = timezone.now()

    formation_open = Stage.objects.filter(
        edition=team.edition,
        kind=StageKind.FORMATION,
        starts_at__lte=now,
        ends_at__gte=now,
    ).exists()

    if not formation_open:
        raise InvitationRejected(
            "Não existe prazo de formação aberto para esta equipe."
        )

    if team.status != TeamStatus.ACTIVE:
        raise InvitationRejected(
            "Equipes desclassificadas não podem enviar convites."
        )

    current_members = TeamMember.objects.filter(
        team=team,
        active=True,
    ).count()

    if current_members >= team.edition.max_members:
        raise InvitationRejected(
            "A equipe já atingiu o limite máximo de integrantes."
        )

    invited_student = (
        Student.objects.select_related("user")
        .filter(pk=student_id)
        .first()
    )

    if invited_student is None:
        raise InvitationRejected("Estudante não encontrado.")

    if (
        invited_student.user.role != UserRole.STUDENT
        or not invited_student.user.is_active
        or not invited_student.user.email_confirmed
    ):
        raise InvitationRejected(
            "O estudante não possui cadastro ativo e confirmado."
        )

    already_in_team = TeamMember.objects.filter(
        edition=team.edition,
        student=invited_student,
        active=True,
    ).exists()

    if already_in_team:
        raise InvitationRejected(
            "O estudante já participa de uma equipe ativa nesta edição."
        )

    pending_invitation = Invitation.objects.filter(
        team=team,
        student=invited_student,
        status=InvitationStatus.PENDING,
    ).exists()

    if pending_invitation:
        raise InvitationRejected(
            "Já existe um convite pendente para este estudante nesta equipe."
        )

    try:
        with transaction.atomic():
            invitation = Invitation.objects.create(
                team=team,
                student=invited_student,
            )
    except IntegrityError as error:
        raise InvitationRejected(
            "Não foi possível enviar o convite. "
            "Verifique se já existe um convite pendente."
        ) from error

    return invitation
