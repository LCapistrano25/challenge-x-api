from django.db import models

from apps.core.models import TimeStampedModel


class MemberNote(TimeStampedModel):
    """Observação do líder sobre um integrante; só professores e admin veem (RF33)."""

    member = models.ForeignKey(
        "teams.TeamMember", on_delete=models.PROTECT, related_name="notes"
    )
    # O líder que registrou; a checagem de liderança fica no caso de uso.
    author = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT, related_name="member_notes"
    )
    text = models.TextField()

    class Meta:
        verbose_name = "observação sobre integrante"
        verbose_name_plural = "observações sobre integrantes"

    def __str__(self):
        return f"{self.member} ({self.created_at:%d/%m/%Y})"
