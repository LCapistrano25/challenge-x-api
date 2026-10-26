from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.core.models import TimeStampedModel
from apps.evaluations.rules import ensure_rectification_within_criterion


class ScoreRectification(TimeStampedModel):
    """Retificação de nota pelo admin, mesmo com a avaliação finalizada (RF14, P-21).

    É o próprio histórico do ajuste: gravada pelo caso de uso rectify_score e
    nunca alterada nem apagada.
    """

    item = models.ForeignKey(
        "evaluations.EvaluationItem",
        on_delete=models.PROTECT,
        related_name="rectifications",
    )
    previous_points = models.DecimalField(max_digits=5, decimal_places=2)
    new_points = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    rectified_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="score_rectifications",
        limit_choices_to={"role": UserRole.ADMIN},
    )
    rectified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "retificação de nota"
        verbose_name_plural = "retificações de nota"
        constraints = [
            models.CheckConstraint(
                condition=Q(new_points__gte=0) & ~Q(new_points=F("previous_points")),
                name="rectification_changes_points",
            ),
            models.CheckConstraint(
                condition=~Q(reason=""), name="rectification_has_reason"
            ),
        ]

    def clean(self):
        if self.item_id and self.new_points is not None:
            ensure_rectification_within_criterion(self)

    def __str__(self):
        return f"{self.item}: {self.previous_points} → {self.new_points}"
