"""RF32, RN24 — Nota zero para a equipe que não entregou a etapa no prazo."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.editions.models import Stage
from apps.evaluations.enums import ScoreStatus
from apps.evaluations.models import StageScore
from apps.evaluations.rules import ensure_stage_is_evaluable
from apps.projects.enums import DeliveryStatus
from apps.projects.models import Project
from apps.projects.selectors import get_delivery_status


@transaction.atomic
def apply_zero_for_missing_submission(
    *, project: Project, stage: Stage
) -> StageScore | None:
    """Grava a nota zero da etapa se o prazo da equipe acabou sem entrega válida.

    O prazo é o da etapa ou a prorrogação da equipe. Devolve None quando a
    equipe ainda pode entregar ou já entregou. Se um zero já gravado deixou de
    valer (prorrogação concedida depois), a nota volta a pendente. Repetir a
    chamada não regrava um zero que já existe.
    Levanta ValidationError se a etapa não tem avaliação do professor.
    """
    ensure_stage_is_evaluable(stage)

    # Trava a nota: o job e um recálculo ao mesmo tempo viram um depois do outro.
    score = (
        StageScore.objects.select_for_update()
        .filter(project=project, stage=stage)
        .first()
    )
    is_zero = score is not None and score.status == ScoreStatus.ZERO_NO_SUBMISSION

    if get_delivery_status(project, stage) != DeliveryStatus.NOT_DELIVERED:
        if is_zero:
            score.value = None
            score.status = ScoreStatus.PENDING
            score.calculated_at = None
            score.save()
        return None
    if is_zero:
        return score

    if score is None:
        score, _ = StageScore.objects.select_for_update().get_or_create(
            project=project, stage=stage
        )
    score.value = Decimal("0.00")
    score.evaluation_count = 0
    score.status = ScoreStatus.ZERO_NO_SUBMISSION
    score.calculated_at = timezone.now()
    score.save()
    return score
