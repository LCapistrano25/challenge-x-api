from django.db import models

from apps.core.models import TimeStampedModel
from apps.editions.rules import ensure_sdg_enabled_in_edition


class Challenge(TimeStampedModel):
    """Desafio de um curso sob uma ODS da edição (RF05, RN11).

    Sem unicidade em (course, sdg): um curso pode ter vários desafios na mesma ODS.
    """

    edition = models.ForeignKey(
        "editions.Edition", on_delete=models.PROTECT, related_name="challenges"
    )
    course = models.ForeignKey(
        "core.Course", on_delete=models.PROTECT, related_name="challenges"
    )
    sdg = models.ForeignKey(
        "core.Sdg", on_delete=models.PROTECT, related_name="challenges"
    )
    description = models.TextField()
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "desafio"
        verbose_name_plural = "desafios"

    def clean(self):
        if self.edition_id and self.sdg_id:
            ensure_sdg_enabled_in_edition(self.edition_id, self.sdg_id)

    def __str__(self):
        return f"{self.course} - ODS {self.sdg.number} (#{self.pk})"
