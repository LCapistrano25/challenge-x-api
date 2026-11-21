from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.editions.enums import EditionStatus, StageKind
from apps.editions.models import Stage
from apps.evaluations.use_cases.apply_zero_for_missing_submission import (
    apply_zero_for_missing_submission,
)
from apps.projects.models import Project


class Command(BaseCommand):
    help = (
        "Grava a nota zero das equipes que não entregaram a etapa no prazo (RN24). "
        "Agendar de hora em hora; repetir não muda nada."
    )

    def handle(self, *args, **options):
        stages = Stage.objects.filter(
            edition__status=EditionStatus.PUBLISHED,
            kind=StageKind.SUBMISSION,
            scored=True,
            # A prorrogação só adia o prazo; o caso de uso confere cada equipe.
            ends_at__lt=timezone.now(),
        )
        applied = 0
        for stage in stages:
            for project in Project.objects.filter(edition_id=stage.edition_id):
                if apply_zero_for_missing_submission(project=project, stage=stage):
                    applied += 1
        self.stdout.write(f"Notas zero aplicadas: {applied}.")
