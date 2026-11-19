"""Congela a formação das equipes após o encerramento do prazo."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.enums import StageKind
from apps.editions.models import Stage
from apps.teams.enums import InvitationStatus, TeamSituation
from apps.teams.models import Invitation, Team
from apps.teams.rules import compute_unmet_requirements


@transaction.atomic
def freeze_formation_period(*, actor: User) -> dict[str, int]:
    """Congela equipes de edições cujo período de formação terminou.

    Equipes sem pendências ficam COMPLETE; as demais ficam INCOMPLETE.
    Convites pendentes são cancelados.
    """
    ensure_actor_is_admin(actor)

    now = timezone.now()

    edition_ids = (
        Stage.objects.filter(
            kind=StageKind.FORMATION,
            starts_at__lte=now,
            ends_at__lt=now,
        )
        .values_list("edition_id", flat=True)
        .distinct()
    )

    teams = Team.objects.select_for_update().filter(
        edition_id__in=edition_ids,
    )

    frozen_teams = 0
    cancelled_invitations = 0

    for team in teams:
        unmet_requirements = compute_unmet_requirements(team)

        situation = (
            TeamSituation.COMPLETE
            if not unmet_requirements
            else TeamSituation.INCOMPLETE
        )

        if team.situation != situation:
            team.situation = situation
            team.save(update_fields=["situation", "updated_at"])
            frozen_teams += 1

        cancelled_invitations += Invitation.objects.filter(
            team=team,
            status=InvitationStatus.PENDING,
        ).update(status=InvitationStatus.CANCELLED, responded_at=now)

    return {
        "frozen_teams": frozen_teams,
        "cancelled_invitations": cancelled_invitations,
    }
