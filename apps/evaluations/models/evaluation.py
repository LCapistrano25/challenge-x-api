from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.evaluations.enums import EvaluationStatus, ScoreStatus
from apps.evaluations.rules import (
    ensure_item_within_criterion,
    ensure_same_edition,
    ensure_within_evaluation_deadline,
)


class Evaluation(TimeStampedModel):
    """Avaliação de um professor sobre a entrega de um projeto numa etapa (RF38).

    O professor precisa estar vinculado ao curso do desafio: regra do caso de uso.
    """

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="evaluations"
    )
    stage = models.ForeignKey(
        "editions.Stage", on_delete=models.PROTECT, related_name="evaluations"
    )
    teacher = models.ForeignKey(
        "accounts.Teacher", on_delete=models.PROTECT, related_name="evaluations"
    )
    comment = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=EvaluationStatus, default=EvaluationStatus.DRAFT
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "stage", "teacher"],
                name="unique_evaluation_per_teacher",
            ),
            models.CheckConstraint(
                condition=Q(status=EvaluationStatus.DRAFT, finalized_at__isnull=True)
                | Q(status=EvaluationStatus.FINALIZED, finalized_at__isnull=False),
                name="evaluation_finalized_at_iff_finalized",
            ),
        ]

    def clean(self):
        if self.project_id and self.stage_id:
            ensure_same_edition(self.project, self.stage.edition_id, "stage")
            ensure_within_evaluation_deadline(self)

    def __str__(self):
        return f"{self.project} — {self.stage} ({self.teacher})"


class EvaluationItem(TimeStampedModel):
    """Pontos de um critério na avaliação; o critério já vem amarrado à etapa."""

    # Item só existe dentro da avaliação (CASCADE).
    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="items"
    )
    stage_criterion = models.ForeignKey(
        "editions.StageCriterion",
        on_delete=models.PROTECT,
        related_name="evaluation_items",
    )
    # O limite superior (max_score do critério) é validado em rules.
    points = models.DecimalField(max_digits=5, decimal_places=2)
    comment = models.TextField(blank=True)

    class Meta:
        verbose_name = "item da avaliação"
        verbose_name_plural = "itens da avaliação"
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "stage_criterion"],
                name="unique_criterion_per_evaluation",
            ),
            models.CheckConstraint(
                condition=Q(points__gte=0), name="evaluation_item_points_gte_0"
            ),
        ]

    def clean(self):
        if self.evaluation_id and self.stage_criterion_id:
            ensure_item_within_criterion(self)

    def __str__(self):
        return f"{self.stage_criterion}: {self.points}"


class StageScore(TimeStampedModel):
    """Nota consolidada do projeto na etapa: a média que a equipe vê (RF32, RF37).

    Guardada de propósito; recalculada a cada avaliação finalizada.
    """

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="stage_scores"
    )
    stage = models.ForeignKey(
        "editions.Stage", on_delete=models.PROTECT, related_name="scores"
    )
    value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    evaluation_count = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=ScoreStatus, default=ScoreStatus.PENDING
    )
    calculated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "nota da etapa"
        verbose_name_plural = "notas da etapa"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "stage"], name="unique_score_per_stage"
            ),
            # Pendente não tem valor; definitiva tem; zero sem entrega vale zero.
            models.CheckConstraint(
                condition=Q(status=ScoreStatus.PENDING, value__isnull=True)
                | Q(status=ScoreStatus.DEFINITIVE, value__isnull=False, value__gte=0)
                | Q(status=ScoreStatus.ZERO_NO_SUBMISSION, value=0),
                name="stage_score_value_matches_status",
            ),
        ]

    def clean(self):
        if self.project_id and self.stage_id:
            ensure_same_edition(self.project, self.stage.edition_id, "stage")

    def __str__(self):
        return f"{self.project} — {self.stage}: {self.value}"
