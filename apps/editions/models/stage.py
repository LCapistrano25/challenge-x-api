from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel
from apps.editions.enums import FieldKind, StageKind
from apps.editions.rules import ensure_criterion_in_stage_edition


class Stage(TimeStampedModel):
    """Etapa da edição, com prazo e valor em pontos (RF07)."""

    edition = models.ForeignKey(
        "editions.Edition", on_delete=models.PROTECT, related_name="stages"
    )
    order = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=StageKind)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    scored = models.BooleanField(default=True)
    # Parte da nota de 0 a 10 que a etapa vale; a soma das etapas fecha em 10.
    max_score = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    min_evaluations = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "etapa"
        verbose_name_plural = "etapas"
        ordering = ["edition", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "order"], name="unique_stage_order_per_edition"
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="stage_ends_after_start"
            ),
            # CHECK aceita NULL como verdadeiro: o isnull explícito barra valor vazio.
            models.CheckConstraint(
                condition=Q(scored=False) | Q(max_score__isnull=False, max_score__gt=0),
                name="stage_scored_has_max_score",
            ),
            models.CheckConstraint(
                condition=Q(min_evaluations__gte=1), name="stage_min_evaluations_gte_1"
            ),
        ]

    def __str__(self):
        return f"{self.edition} - {self.order}. {self.name}"


class StageSubmissionField(TimeStampedModel):
    """Link ou arquivo que a entrega da etapa deve conter (RF07)."""

    # Campo de configuração da etapa: sem a etapa não faz sentido (CASCADE).
    stage = models.ForeignKey(
        Stage, on_delete=models.CASCADE, related_name="submission_fields"
    )
    kind = models.CharField(max_length=10, choices=FieldKind)
    label = models.CharField(max_length=150, blank=True)
    required = models.BooleanField(default=True)
    formats = models.CharField(max_length=200, blank=True)
    max_size_mb = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "campo de entrega"
        verbose_name_plural = "campos de entrega"

    def __str__(self):
        return self.label or self.get_kind_display()


class StageCriterion(TimeStampedModel):
    """Pontuação máxima de um critério numa etapa (RF08)."""

    # Linha de configuração da etapa (CASCADE); o critério é protegido.
    stage = models.ForeignKey(
        Stage, on_delete=models.CASCADE, related_name="criterion_links"
    )
    criterion = models.ForeignKey(
        "editions.Criterion", on_delete=models.PROTECT, related_name="stage_links"
    )
    max_score = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        verbose_name = "critério da etapa"
        verbose_name_plural = "critérios da etapa"
        constraints = [
            models.UniqueConstraint(
                fields=["stage", "criterion"], name="unique_criterion_per_stage"
            ),
            models.CheckConstraint(
                condition=Q(max_score__gt=0), name="stage_criterion_max_score_gt_0"
            ),
        ]

    def clean(self):
        if self.stage_id and self.criterion_id:
            ensure_criterion_in_stage_edition(self.stage, self.criterion)

    def __str__(self):
        return f"{self.stage} - {self.criterion}"
