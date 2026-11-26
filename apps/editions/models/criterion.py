from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel
from apps.editions.exceptions import EditionError
from apps.editions.rules import (
    ensure_criterion_can_be_saved,
    ensure_criterion_values_are_valid,
)


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
                Lower("name"), "edition", name="unique_criterion_name_per_edition"
            ),
            models.UniqueConstraint(
                fields=["edition", "tiebreak_order"],
                name="unique_tiebreak_order_per_edition",
            ),
        ]

    def clean(self):
        super().clean()
        ensure_criterion_values_are_valid(
            name=self.name, tiebreak_order=self.tiebreak_order
        )
        self.name = self.name.strip()
        try:
            ensure_criterion_can_be_saved(
                criterion_id=self.pk, edition_id=self.edition_id
            )
        except EditionError as error:
            raise ValidationError(str(error), code=error.code) from error

    def __str__(self):
        return self.name
