"""RF32, RF37 — Recalcular a nota da etapa a partir das avaliações finalizadas."""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.editions.models import Stage
from apps.evaluations.enums import EvaluationStatus, ScoreStatus
from apps.evaluations.models import Evaluation, StageScore
from apps.projects.models import Project


@transaction.atomic
def recalculate_stage_score(*, project: Project, stage: Stage) -> StageScore:
    """Média simples dos totais das avaliações finalizadas (RN25).

    Com menos avaliações que o mínimo da etapa a nota fica pendente e sem valor.
    """
    # Trava a nota antes de ler os totais: dois professores finalizando juntos
    # recalculam um depois do outro e o segundo vê as duas avaliações.
    score, _ = StageScore.objects.select_for_update().get_or_create(
        project=project, stage=stage
    )
    totals = list(
        Evaluation.objects.filter(
            project=project, stage=stage, status=EvaluationStatus.FINALIZED
        )
        .annotate(total=Sum("items__points"))
        .values_list("total", flat=True)
    )
    count = len(totals)
    if count >= stage.min_evaluations:
        status = ScoreStatus.DEFINITIVE
        value = (sum(totals, Decimal(0)) / count).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        status, value = ScoreStatus.PENDING, None

    score.value = value
    score.evaluation_count = count
    score.status = status
    score.calculated_at = timezone.now()
    score.save()
    return score
