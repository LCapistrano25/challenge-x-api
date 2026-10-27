"""RF14 — Retificar nota de um critério, com histórico imutável (P-21)."""

from decimal import Decimal

from django.db import transaction

from apps.accounts.models import User
from apps.evaluations.models import EvaluationItem, ScoreRectification


@transaction.atomic
def rectify_score(
    *, actor: User, item: EvaluationItem, new_points: Decimal, reason: str
) -> ScoreRectification:
    """Troca os pontos do item e grava o valor anterior, o novo e a justificativa.

    Vale também para avaliação finalizada e fora do prazo: é o ajuste do admin.
    Levanta ValidationError se o actor não for admin, sem justificativa, com os
    mesmos pontos ou acima do máximo do critério.
    """
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
    return rectification
