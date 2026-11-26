from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q

from apps.core.models import TimeStampedModel
from apps.editions.enums import FieldKind, StageKind
from apps.editions.exceptions import EditionClosed
from apps.editions.models.edition import Edition
from apps.editions.rules import (
    ensure_criterion_in_stage_edition,
    ensure_edition_not_closed,
    ensure_formation_stage_is_unique,
    ensure_stage_max_score_fits,
    ensure_stage_scoring_can_change,
    ensure_stage_submission_field_is_valid,
    ensure_stage_submission_fields_are_unused,
    ensure_stage_values_are_valid,
)


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
    # Prazo dos professores, depois do fim das entregas (RF38, P-19).
    evaluation_ends_at = models.DateTimeField(null=True, blank=True)
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
            models.CheckConstraint(
                condition=Q(scored=False) | Q(evaluation_ends_at__isnull=False),
                name="stage_scored_has_evaluation_deadline",
            ),
            models.CheckConstraint(
                condition=Q(evaluation_ends_at__isnull=True)
                | Q(evaluation_ends_at__gt=F("ends_at")),
                name="stage_evaluation_after_submission",
            ),
            # A etapa final não compõe a nota de 0 a 10 (RF07, P-20).
            models.CheckConstraint(
                condition=~Q(kind=StageKind.FINAL) | Q(scored=False),
                name="stage_final_not_scored",
            ),
        ]

    @transaction.atomic
    def clean(self):
        super().clean()
        ensure_stage_values_are_valid(self)
        previous = (
            type(self).objects.filter(pk=self.pk).values("edition_id", "scored").first()
            if self.pk is not None
            else None
        )
        edition_ids = {self.edition_id}
        if previous is not None:
            edition_ids.add(previous["edition_id"])
        # No Admin, a transação externa do formulário mantém a trava até salvar.
        editions = (
            Edition.objects.select_for_update()
            .filter(pk__in=edition_ids)
            .order_by("pk")
        )
        for edition in editions:
            try:
                ensure_edition_not_closed(edition)
            except EditionClosed as error:
                raise ValidationError(str(error), code=error.code) from error
        if self.edition_id is not None:
            ensure_formation_stage_is_unique(self)
            ensure_stage_max_score_fits(self)
        if previous is not None:
            ensure_stage_scoring_can_change(self, previously_scored=previous["scored"])

    def __str__(self):
        return f"{self.edition} - {self.order}. {self.name}"


class StageSubmissionField(TimeStampedModel):
    """Link, arquivo, canvas ou SWOT que a entrega da etapa deve conter (RF07)."""

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
        constraints = [
            # Canvas e SWOT são preenchidos no sistema: não têm formato nem tamanho.
            models.CheckConstraint(
                condition=~Q(kind__in=[FieldKind.CANVAS, FieldKind.SWOT])
                | (Q(formats="") & Q(max_size_mb__isnull=True)),
                name="submission_field_canvas_swot_without_file_options",
            ),
        ]

    def clean(self):
        super().clean()
        try:
            ensure_stage_submission_field_is_valid(self)
            if (
                self.pk is not None
                and type(self)
                .objects.filter(pk=self.pk)
                .exclude(kind=self.kind)
                .exists()
            ):
                ensure_stage_submission_fields_are_unused([self.pk])
        except ValidationError as error:
            raise ValidationError(error.messages) from error

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
        # No admin a etapa nova ainda não tem id quando os critérios são validados.
        has_stage = self.stage_id or StageCriterion.stage.is_cached(self)
        if has_stage and self.criterion_id:
            ensure_criterion_in_stage_edition(self.stage, self.criterion)

    def __str__(self):
        return f"{self.stage} - {self.criterion}"
