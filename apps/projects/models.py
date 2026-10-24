from uuid import uuid4

from django.db import models


class Project(models.Model):
    """Projeto desenvolvido por uma equipe no Desafio X."""

    # Os relacionamentos com equipe e desafio serão definidos
    # após a integração com BM3 e BM4.

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Projeto #{self.pk}"


class Submission(models.Model):
    """Entrega vinculada a um projeto."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="submissions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Entrega #{self.pk} — Projeto #{self.project_id}"


class SubmissionVersion(models.Model):
    """Versão de uma entrega."""

    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    number = models.PositiveIntegerField()
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "number"],
                name="unique_submission_version_number",
            ),
            models.CheckConstraint(
                condition=models.Q(number__gte=1),
                name="submission_version_number_gte_1",
            ),
        ]

    def __str__(self):
        return f"Entrega #{self.submission_id} — Versão {self.number}"


class SubmissionItem(models.Model):
    """Link associado a uma versão da entrega."""

    version = models.ForeignKey(
        SubmissionVersion,
        on_delete=models.CASCADE,
        related_name="items",
    )
    url = models.URLField(max_length=500)

    def __str__(self):
        return f"Item #{self.pk} — Versão #{self.version_id}"


class SubmissionReceipt(models.Model):
    """Comprovante de recebimento de uma versão."""

    version = models.ForeignKey(
        SubmissionVersion,
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    receipt_code = models.UUIDField(
        default=uuid4,
        unique=True,
        editable=False,
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"Comprovante {self.receipt_code}"
