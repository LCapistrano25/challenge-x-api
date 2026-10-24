from django.db import models
from django.db.models import Q


class TimeStampedModel(models.Model):
    """Base abstrata com datas de criação e atualização."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Course(TimeStampedModel):
    """Curso de graduação participante do Desafio X (RF03, RN10)."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.CharField(max_length=20, unique=True)
    # Quantidade de períodos: identifica quem está no último ano (RN10).
    term_count = models.PositiveSmallIntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "curso"
        verbose_name_plural = "cursos"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(term_count__in=[8, 10]),
                name="course_term_count_8_or_10",
            ),
        ]

    def __str__(self):
        return self.name


class Sdg(TimeStampedModel):
    """Objetivo de Desenvolvimento Sustentável, catálogo global (RF04)."""

    number = models.PositiveSmallIntegerField(unique=True)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "ODS"
        verbose_name_plural = "ODS"
        ordering = ["number"]
        constraints = [
            models.CheckConstraint(
                condition=Q(number__gte=1, number__lte=17),
                name="sdg_number_between_1_and_17",
            ),
        ]

    def __str__(self):
        return f"ODS {self.number} - {self.title}"
