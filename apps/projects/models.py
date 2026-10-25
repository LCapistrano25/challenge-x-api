from uuid import uuid4

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.editions.enums import FieldKind
from apps.projects.enums import ProjectStatus
from apps.projects.rules import (
    ensure_project_in_team_edition,
    ensure_stage_in_project_edition,
)


def new_verification_code():
    return uuid4().hex


class Project(TimeStampedModel):
    """Projeto da equipe; curso e ODS vêm do desafio (RF29, RF30, RF34)."""

    team = models.OneToOneField(
        "teams.Team", on_delete=models.PROTECT, related_name="project"
    )
    # Repetido da equipe para a unicidade do título; rules garante que não diverge.
    edition = models.ForeignKey(
        "editions.Edition", on_delete=models.PROTECT, related_name="projects"
    )
    title = models.CharField(max_length=200)
    summary = models.TextField()
    objective = models.TextField(blank=True)
    challenge = models.ForeignKey(
        "editions.Challenge", on_delete=models.PROTECT, related_name="projects"
    )
    category = models.ForeignKey(
        "editions.Category",
        on_delete=models.PROTECT,
        related_name="projects",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=ProjectStatus, default=ProjectStatus.IN_PROGRESS
    )

    class Meta:
        verbose_name = "projeto"
        verbose_name_plural = "projetos"
        constraints = [
            # Título único na edição sem diferenciar maiúsculas (RN03).
            models.UniqueConstraint(
                "edition", Lower("title"), name="unique_project_title_per_edition"
            ),
        ]

    def clean(self):
        if self.team_id and self.edition_id and self.challenge_id:
            ensure_project_in_team_edition(self)

    def __str__(self):
        return self.title


class Submission(TimeStampedModel):
    """Entrega do projeto numa etapa; sem status nem versão válida guardados (RF31).

    A versão que vale é calculada em selectors.get_valid_version().
    """

    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="submissions"
    )
    stage = models.ForeignKey(
        "editions.Stage", on_delete=models.PROTECT, related_name="submissions"
    )

    class Meta:
        verbose_name = "entrega"
        verbose_name_plural = "entregas"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "stage"], name="unique_submission_per_stage"
            ),
        ]

    def clean(self):
        if self.project_id and self.stage_id:
            ensure_stage_in_project_edition(self)

    def __str__(self):
        return f"{self.project} — {self.stage}"


class SubmissionVersion(TimeStampedModel):
    """Cada envio do líder; nenhuma versão muda depois de criada (RF31)."""

    submission = models.ForeignKey(
        Submission, on_delete=models.PROTECT, related_name="versions"
    )
    number = models.PositiveIntegerField()
    submitted_by = models.ForeignKey(
        "accounts.Student",
        on_delete=models.PROTECT,
        related_name="submission_versions",
    )
    submitted_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "versão da entrega"
        verbose_name_plural = "versões da entrega"
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "number"],
                name="unique_submission_version_number",
            ),
            models.CheckConstraint(
                condition=Q(number__gte=1),
                name="submission_version_number_gte_1",
            ),
        ]

    def __str__(self):
        return f"{self.submission} — versão {self.number}"


class SubmissionItem(TimeStampedModel):
    """Link ou arquivo de uma versão, respondendo a um campo da etapa."""

    # Item só existe dentro da versão (CASCADE, como o guia permite).
    version = models.ForeignKey(
        SubmissionVersion, on_delete=models.CASCADE, related_name="items"
    )
    field = models.ForeignKey(
        "editions.StageSubmissionField",
        on_delete=models.PROTECT,
        related_name="items",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=10, choices=FieldKind)
    link = models.URLField(max_length=1000, blank=True)
    file_url = models.CharField(max_length=1000, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "item da entrega"
        verbose_name_plural = "itens da entrega"
        constraints = [
            models.CheckConstraint(
                condition=(Q(kind=FieldKind.LINK) & ~Q(link=""))
                | (Q(kind=FieldKind.FILE) & ~Q(file_url="")),
                name="submission_item_matches_kind",
            ),
        ]

    def __str__(self):
        return self.link or self.file_name or f"Item #{self.pk}"


class SubmissionReceipt(TimeStampedModel):
    """Comprovante de uma versão, com código de verificação próprio (RF31)."""

    version = models.OneToOneField(
        SubmissionVersion, on_delete=models.PROTECT, related_name="receipt"
    )
    verification_code = models.CharField(
        max_length=50, unique=True, default=new_verification_code, editable=False
    )
    file_url = models.CharField(max_length=1000, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "comprovante de entrega"
        verbose_name_plural = "comprovantes de entrega"
        ordering = ["-generated_at"]

    def __str__(self):
        return f"Comprovante {self.verification_code}"
