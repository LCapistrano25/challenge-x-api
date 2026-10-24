from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel
from apps.editions.enums import EditionStatus, FieldKind, StageKind


class Edition(TimeStampedModel):
    """Edição do Desafio X, identificada por ano e semestre (RF09, RF47, RF48)."""

    year = models.PositiveSmallIntegerField()
    semester = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20, choices=EditionStatus, default=EditionStatus.SETUP
    )
    regulation_file = models.FileField(upload_to="regulations/", blank=True)
    min_members = models.PositiveSmallIntegerField(default=3)
    max_members = models.PositiveSmallIntegerField(default=5)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "edição"
        verbose_name_plural = "edições"
        ordering = ["-year", "-semester"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "semester"], name="unique_edition_year_semester"
            ),
            models.CheckConstraint(
                condition=Q(semester__in=[1, 2]), name="edition_semester_1_or_2"
            ),
            models.CheckConstraint(
                condition=Q(min_members__gte=1, max_members__gte=F("min_members")),
                name="edition_member_limits_valid",
            ),
        ]

    def __str__(self):
        return self.name or f"Desafio X {self.year}/{self.semester}"


class EditionSdg(TimeStampedModel):
    """ODS aceita na edição (RN09)."""

    edition = models.ForeignKey(
        Edition, on_delete=models.PROTECT, related_name="sdg_links"
    )
    sdg = models.ForeignKey(
        "core.Sdg", on_delete=models.PROTECT, related_name="edition_links"
    )

    class Meta:
        verbose_name = "ODS da edição"
        verbose_name_plural = "ODS da edição"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "sdg"], name="unique_sdg_per_edition"
            ),
        ]

    def __str__(self):
        return f"{self.edition} - {self.sdg}"


class Category(TimeStampedModel):
    """Categoria de projeto da edição (RF49)."""

    edition = models.ForeignKey(
        Edition, on_delete=models.PROTECT, related_name="categories"
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"

    def __str__(self):
        return self.name


class Challenge(TimeStampedModel):
    """Desafio de um curso sob uma ODS da edição (RF05, RN11).

    Sem unicidade em (course, sdg): um curso pode ter vários desafios na mesma ODS.
    """

    edition = models.ForeignKey(
        Edition, on_delete=models.PROTECT, related_name="challenges"
    )
    course = models.ForeignKey(
        "core.Course", on_delete=models.PROTECT, related_name="challenges"
    )
    sdg = models.ForeignKey(
        "core.Sdg", on_delete=models.PROTECT, related_name="challenges"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "desafio"
        verbose_name_plural = "desafios"

    def clean(self):
        # A ODS precisa estar habilitada na edição (RN09); envolve outra tabela.
        if (
            self.edition_id
            and self.sdg_id
            and not EditionSdg.objects.filter(
                edition_id=self.edition_id, sdg_id=self.sdg_id
            ).exists()
        ):
            raise ValidationError({"sdg": "A ODS não está habilitada nesta edição."})

    def __str__(self):
        return self.title


class Stage(TimeStampedModel):
    """Etapa da edição, com prazo e valor em pontos (RF07)."""

    edition = models.ForeignKey(
        Edition, on_delete=models.PROTECT, related_name="stages"
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
    label = models.CharField(max_length=150)
    required = models.BooleanField(default=True)
    formats = models.CharField(max_length=200, blank=True)
    max_size_mb = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "campo de entrega"
        verbose_name_plural = "campos de entrega"

    def __str__(self):
        return self.label


class Criterion(TimeStampedModel):
    """Critério de avaliação com a rubrica das faixas (RF06)."""

    edition = models.ForeignKey(
        Edition, on_delete=models.PROTECT, related_name="criteria"
    )
    name = models.CharField(max_length=150)
    rubric = models.TextField(blank=True)
    tiebreak_order = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "critério"
        verbose_name_plural = "critérios"

    def __str__(self):
        return self.name


class StageCriterion(TimeStampedModel):
    """Pontuação máxima de um critério numa etapa (RF08)."""

    # Linha de configuração da etapa (CASCADE); o critério é protegido.
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name="criteria")
    criterion = models.ForeignKey(
        Criterion, on_delete=models.PROTECT, related_name="stage_links"
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
        if (
            self.stage_id
            and self.criterion_id
            and self.stage.edition_id != self.criterion.edition_id
        ):
            raise ValidationError("O critério pertence a outra edição.")

    def __str__(self):
        return f"{self.stage} - {self.criterion}"


class EditionReviewer(TimeStampedModel):
    """Avaliador externo convidado para a edição (RF11)."""

    edition = models.ForeignKey(
        Edition, on_delete=models.PROTECT, related_name="reviewers"
    )
    reviewer = models.ForeignKey(
        "accounts.ExternalReviewer", on_delete=models.PROTECT, related_name="editions"
    )
    # Nulo: avalia os finalistas de todos os cursos da edição.
    course = models.ForeignKey(
        "core.Course",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "avaliador da edição"
        verbose_name_plural = "avaliadores da edição"

    def __str__(self):
        return f"{self.edition} - {self.reviewer}"
