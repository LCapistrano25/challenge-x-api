from django.core.management.base import BaseCommand, CommandError

from apps.accounts.enums import UserRole
from apps.accounts.models import User
from apps.teams.use_cases.freeze_formation_period import (
    freeze_formation_period,
)


class Command(BaseCommand):
    help = "Congela a formação das equipes após o encerramento do prazo."

    def handle(self, *args, **options):
        actor = (
            User.objects.filter(
                role=UserRole.ADMIN,
                is_active=True,
            )
            .order_by("pk")
            .first()
        )

        if actor is None:
            raise CommandError(
                "Não existe administrador ativo para executar o congelamento."
            )

        result = freeze_formation_period(actor=actor)

        self.stdout.write(
            self.style.SUCCESS(
                "Congelamento concluído: "
                f"{result['frozen_teams']} equipe(s) atualizada(s) e "
                f"{result['cancelled_invitations']} convite(s) cancelado(s)."
            )
        )
