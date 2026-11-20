from django.db import transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.editions.enums import StageKind
from apps.editions.models import Stage
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.teams.enums import InvitationStatus, MemberRole, RequestStatus, TeamStatus
from apps.teams.models import Invitation, JoinRequest, Team, TeamMember


class LeaveTeamRejected(Exception):
    """A saída da equipe foi rejeitada por uma regra de negócio."""


@transaction.atomic
def leave_team(
    *,
    actor: User,
    team_id: int,
) -> TeamMember:
    """Encerra o vínculo do acadêmico com sua equipe, preservando o histórico.

    O líder só sai depois de transferir a liderança, a não ser que esteja sozinho:
    aí a saída desfaz a equipe (status DISBANDED) e cancela os convites e as
    solicitações pendentes, para o aluno poder entrar em outra equipe.
    """
    if actor.role != UserRole.STUDENT:
        raise LeaveTeamRejected("Somente alunos podem sair de equipes.")

    student = Student.objects.filter(user=actor).first()

    if student is None:
        raise LeaveTeamRejected("O perfil de aluno não foi encontrado.")

    team = Team.objects.select_for_update().filter(pk=team_id).first()

    if team is None:
        raise LeaveTeamRejected("Equipe não encontrada.")

    membership = (
        TeamMember.objects.select_for_update()
        .filter(
            team=team,
            student=student,
            active=True,
        )
        .first()
    )

    if membership is None:
        raise LeaveTeamRejected("O aluno não possui vínculo ativo com esta equipe.")

    now = timezone.now()

    formation_open = Stage.objects.filter(
        edition=team.edition,
        kind=StageKind.FORMATION,
        starts_at__lte=now,
        ends_at__gte=now,
    ).exists()

    if not formation_open:
        raise LeaveTeamRejected("Não existe prazo de formação aberto para esta equipe.")

    if membership.role == MemberRole.LEADER:
        has_other_members = (
            TeamMember.objects.filter(team=team, active=True)
            .exclude(pk=membership.pk)
            .exists()
        )
        if has_other_members:
            raise LeaveTeamRejected("Transfira a liderança antes de sair da equipe.")
        _disband_team(team, now)

    membership.active = False
    membership.left_at = now
    membership.save(update_fields=["active", "left_at", "updated_at"])

    project = getattr(team, "project", None)

    if (
        project is not None
        and project.challenge_id is not None
        and project.challenge.course_id == student.course_id
    ):
        has_course_representative = TeamMember.objects.filter(
            team=team,
            active=True,
            student__course_id=project.challenge.course_id,
        ).exists()

        if not has_course_representative:
            _invalidate_challenge(project)

    remaining_members = TeamMember.objects.filter(
        team=team,
        active=True,
    ).select_related("student__user")

    for member in remaining_members:
        create_notification(
            user=member.student.user,
            notification_type=NotificationType.TEAM,
            title="Integrante saiu da equipe",
            message=f"{student.user.name} saiu da equipe {team.name}.",
            link=f"/equipes/{team.id}",
        )

    return membership


def _disband_team(team: Team, now) -> None:
    team.status = TeamStatus.DISBANDED
    team.save(update_fields=["status", "updated_at"])
    Invitation.objects.filter(team=team, status=InvitationStatus.PENDING).update(
        status=InvitationStatus.CANCELLED, updated_at=now
    )
    JoinRequest.objects.filter(team=team, status=RequestStatus.PENDING).update(
        status=RequestStatus.CANCELLED, updated_at=now
    )


def _invalidate_challenge(project) -> None:
    """Encaminha a invalidação ao caso de uso do app projects."""
    from apps.projects.use_cases.invalidate_challenge import invalidate_challenge

    invalidate_challenge(project=project)
