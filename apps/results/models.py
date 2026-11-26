from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.projects.models import new_verification_code
from apps.results.enums import CertificateKind


class ProjectResult(TimeStampedModel):
    """Resultado publicado e homologado do projeto (RF15, RF16).

    Consolidado de propósito, como a nota da etapa.
    """

    project = models.OneToOneField(
        "projects.Project", on_delete=models.PROTECT, related_name="result"
    )
    # Soma das notas das etapas, de 0 a 10.
    final_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    # Posição no curso, usada na seleção de finalistas.
    course_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    # Posição do finalista na categoria, na edição inteira (pódio, D-01).
    category_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    finalist = models.BooleanField(default=False)
    # Colocação premiada (1, 2 ou 3); vazio quando não premiado.
    award = models.PositiveSmallIntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "resultado do projeto"
        verbose_name_plural = "resultados dos projetos"
        constraints = [
            models.CheckConstraint(
                condition=Q(final_score__isnull=True)
                | Q(final_score__gte=0, final_score__lte=10),
                name="project_result_final_score_0_to_10",
            ),
            models.CheckConstraint(
                condition=Q(award__isnull=True) | Q(award__in=[1, 2, 3]),
                name="project_result_award_1_to_3",
            ),
        ]

    def __str__(self):
        return f"{self.project}: {self.final_score}"


class CertificateTemplate(TimeStampedModel):
    """Modelo de certificado da edição, um por tipo (RF17)."""

    edition = models.ForeignKey(
        "editions.Edition",
        on_delete=models.PROTECT,
        related_name="certificate_templates",
    )
    kind = models.CharField(max_length=20, choices=CertificateKind)
    template_url = models.CharField(max_length=1000, blank=True)
    # Nomes, cargos e imagens das assinaturas digitais.
    signatures = models.TextField(blank=True)

    class Meta:
        verbose_name = "modelo de certificado"
        verbose_name_plural = "modelos de certificado"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "kind"], name="unique_template_per_kind"
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.edition}"


class Certificate(TimeStampedModel):
    """Certificado emitido, com código de verificação próprio (RF17).

    O modelo traz a edição e o tipo, sem repetir as duas colunas aqui.
    """

    template = models.ForeignKey(
        CertificateTemplate, on_delete=models.PROTECT, related_name="certificates"
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="certificates"
    )
    # 20h ou 40h, conforme o regulamento.
    workload_hours = models.PositiveSmallIntegerField(null=True, blank=True)
    verification_code = models.CharField(
        max_length=50, unique=True, default=new_verification_code, editable=False
    )
    file_url = models.CharField(max_length=1000, blank=True)
    issued_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "certificado"
        verbose_name_plural = "certificados"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "user"], name="unique_certificate_per_user"
            ),
            models.CheckConstraint(
                condition=Q(workload_hours__isnull=True)
                | Q(workload_hours__in=[20, 40]),
                name="certificate_workload_20_or_40",
            ),
        ]

    def __str__(self):
        return f"{self.template} — {self.user}"
