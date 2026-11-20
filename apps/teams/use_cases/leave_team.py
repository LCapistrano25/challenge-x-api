from django.db import transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.teams.enums import InvitationStatus, MemberRole, RequestStatus, TeamStatus
from apps.teams.models import Invitation, JoinRequest, Team, TeamMember
from apps.teams.rules import (
    FORMATION_EXTENSION,
    FORMATION_LAST_HOURS,
    get_open_formation_stage,
)


class LeaveTeamRejected(Exception):
    """A saída da equipe foi rejeitada por uma regra de negócio."""


class LeaveBelowMinimum(LeaveTeamRejected):
    """A saída deixa a equipe abaixo do mínimo e ainda não foi confirmada."""

    code = "leave_below_minimum"


@transaction.atomic
def leave_team(
    *,
    actor: User,
    team_id: int,
    confirm: bool = False,
) -> TeamMember:
    """Encerra o vínculo do acadêmico com sua equipe, preservando o histórico.

    O líder só sai depois de transferir a liderança, a não ser que esteja sozinho:
    aí a saída desfaz a equipe (status DISBANDED) e cancela os convites e as
    solicitações pendentes, para o aluno poder entrar em outra equipe.

    Se a saída deixa a equipe com algum integrante, mas abaixo do mínimo da
    edição, ela só vale com confirm=True (LeaveBelowMinimum): perto do fim do
    prazo a equipe não tem tempo de repor a vaga.
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

    formation_stage = get_open_formation_stage(team.edition, now)

    if formation_stage is None:
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

    remaining = (
        TeamMember.objects.filter(team=team, active=True)
        .exclude(pk=membership.pk)
        .count()
    )
    minimum = team.edition.min_members
    below_minimum = 0 < remaining < minimum
    if below_minimum and not confirm:
        raise LeaveBelowMinimum(
            f"Sua saída deixa a equipe com {remaining} de {minimum} integrantes. "
            "Confirme para sair."
        )

    # Saída em cima da hora que derruba a equipe: ela ganha tempo para repor a vaga.
    extension_granted = (
        below_minimum
        and team.formation_extended_until is None
        and formation_stage.ends_at - now <= FORMATION_LAST_HOURS
    )
    if extension_granted:
        team.formation_extended_until = formation_stage.ends_at + FORMATION_EXTENSION
        team.save(update_fields=["formation_extended_until", "updated_at"])

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
            message=(
                f"{student.user.name} saiu da equipe {team.name}."
                + (
                    f" A equipe ficou com {remaining} de {minimum} integrantes."
                    if below_minimum
                    else ""
                )
                + (
                    " A equipe tem até "
                    f"{timezone.localtime(team.formation_extended_until):%d/%m %H:%M}"
                    " para repor a vaga."
                    if extension_granted
                    else ""
                )
            ),
            link=f"/equipes/{team.id}",
        )

    return membership


def _disband_team(team: Team, now) -> None:
    team.status = TeamStatus.DISBANDED
    team.save(update_fields=["status", "updated_at"])
    invitations = Invitation.objects.filter(team=team, status=InvitationStatus.PENDING)
    requests = JoinRequest.objects.filter(team=team, status=RequestStatus.PENDING)
    # Avisa quem esperava resposta antes de cancelar, senão o convite some em silêncio.
    waiting = [*invitations.select_related("student__user")]
    waiting += [*requests.select_related("student__user")]
    for item in waiting:
        create_notification(
            user=item.student.user,
            notification_type=NotificationType.TEAM,
            title="Equipe desfeita",
            message=(
                f"A equipe {team.name} foi desfeita; "
                "o convite ou a solicitação foi cancelado."
            ),
        )
    invitations.update(status=InvitationStatus.CANCELLED, updated_at=now)
    requests.update(status=RequestStatus.CANCELLED, updated_at=now)


def _invalidate_challenge(project) -> None:
    """Encaminha a invalidação ao caso de uso do app projects."""
    from apps.projects.use_cases.invalidate_challenge import invalidate_challenge

    invalidate_challenge(project=project)
