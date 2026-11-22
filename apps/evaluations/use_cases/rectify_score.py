"""RF14 — Retificar nota de um critério, com histórico imutável (P-21)."""

from decimal import Decimal

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.evaluations.models import EvaluationItem, ScoreRectification
from apps.evaluations.use_cases.recalculate_stage_score import recalculate_stage_score


@transaction.atomic
def rectify_score(
    *, actor: User, item: EvaluationItem, new_points: Decimal, reason: str
) -> ScoreRectification:
    """Troca os pontos do item e grava o valor anterior, o novo e a justificativa.

    Vale para avaliação finalizada, mesmo fora do prazo: é o ajuste do admin.
    Levanta NotAdminActor se o actor não for admin e ValidationError se a
    avaliação não estiver finalizada, a edição estiver encerrada, sem
    justificativa, com os mesmos pontos ou acima do máximo do critério.
    """
    ensure_actor_is_admin(actor)
    item = EvaluationItem.objects.select_for_update().get(pk=item.pk)
    rectification = ScoreRectification(
        item=item,
        previous_points=item.points,
        new_points=new_points,
        reason=reason,
        rectified_by=actor,
    )
    rectification.full_clean()
    rectification.save()
    item.points = new_points
    item.save(update_fields=["points", "updated_at"])
    evaluation = item.evaluation
    # A nota que a equipe vê acompanha o ajuste.
    recalculate_stage_score(project=evaluation.project, stage=evaluation.stage)
    return rectification
