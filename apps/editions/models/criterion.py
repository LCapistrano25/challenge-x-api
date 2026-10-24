from django.db import models

from apps.core.models import TimeStampedModel


class Criterion(TimeStampedModel):
    """Critério de avaliação com a rubrica das faixas (RF06)."""

    edition = models.ForeignKey(
        "editions.Edition", on_delete=models.PROTECT, related_name="criteria"
    )
    name = models.CharField(max_length=150)
    rubric = models.TextField(blank=True)
    # Nulo: não desempata. 1 e 2 reproduzem a ordem do Art. 24.
    tiebreak_order = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "critério"
        verbose_name_plural = "critérios"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "tiebreak_order"],
                name="unique_tiebreak_order_per_edition",
            ),
        ]

    def __str__(self):
        return self.name
