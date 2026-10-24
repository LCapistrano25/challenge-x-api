from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel
from apps.editions.enums import EditionStatus


class Edition(TimeStampedModel):
    """Edição do Desafio X, identificada por ano e semestre (RF09, RF47, RF48)."""

    year = models.PositiveSmallIntegerField()
    semester = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20, choices=EditionStatus, default=EditionStatus.SETUP
    )
    regulation_url = models.URLField(max_length=500, blank=True)
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

    def delete(self, *args, **kwargs):
        # Challenge aponta para Sdg, não para esta linha: o banco não protege.
        # shortcut: queryset.delete() não passa por aqui; hoje só o admin apaga.
        from apps.editions.rules import ensure_sdg_not_used_by_challenges

        ensure_sdg_not_used_by_challenges(self.edition_id, self.sdg_id)
        return super().delete(*args, **kwargs)

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
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "name"], name="unique_category_name_per_edition"
            ),
        ]

    def __str__(self):
        return self.name


class EditionReviewer(TimeStampedModel):
    """Avaliador externo convidado para a edição (RF11)."""

    edition = models.ForeignKey(
        Edition, on_delete=models.PROTECT, related_name="reviewers"
    )
    reviewer = models.ForeignKey(
        "accounts.ExternalReviewer",
        on_delete=models.PROTECT,
        related_name="edition_links",
    )
    # Nulo: avalia os finalistas de todos os cursos da edição.
    course = models.ForeignKey(
        "core.Course",
        on_delete=models.PROTECT,
        related_name="edition_reviewers",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "avaliador da edição"
        verbose_name_plural = "avaliadores da edição"
        constraints = [
            models.UniqueConstraint(
                fields=["reviewer", "edition"], name="unique_reviewer_per_edition"
            ),
        ]

    def __str__(self):
        return f"{self.edition} - {self.reviewer}"
