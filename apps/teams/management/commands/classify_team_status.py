import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.editions.enums import EditionStatus, StageKind
from apps.editions.models import Stage
from apps.teams.enums import TeamStatus
from apps.teams.models import Team
from apps.teams.rules import is_formation_open_for_team
from apps.teams.use_cases.flag_team_status import flag_team_status

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Classifica a situação das equipes após o período de formação (UC40). "
        "Pode ser executado novamente para tentar processar equipes pendentes."
    )

    def handle(self, *args, **options):
        teams = Team.objects.filter(
            edition__status=EditionStatus.PUBLISHED,
            status=TeamStatus.ACTIVE,
            situation__isnull=True,
        ).order_by("pk")

        classified = 0
        failed = 0
        now = timezone.now()

        for team in teams.iterator():
            formation_stage = Stage.objects.filter(
                edition=team.edition,
                kind=StageKind.FORMATION,
            ).first()

            if formation_stage is not None and (
                now < formation_stage.starts_at
                or is_formation_open_for_team(team, now)
            ):
                continue

            try:
                flag_team_status(team_id=team.pk)
                classified += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Falha ao classificar a equipe %s. Será tentada novamente "
                    "na próxima execução.",
                    team.pk,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Equipes classificadas: {classified}. Falhas: {failed}."
            )
        )
