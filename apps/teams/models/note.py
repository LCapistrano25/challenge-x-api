from django.db import models

from apps.core.models import TimeStampedModel


class MemberNote(TimeStampedModel):
    """Observação do líder sobre um integrante; só professores e admin veem (RF33)."""

    member = models.ForeignKey(
        "teams.TeamMember", on_delete=models.PROTECT, related_name="notes"
    )
    author = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT, related_name="member_notes"
    )
    stage = models.ForeignKey(
        "editions.Stage",
        on_delete=models.PROTECT,
        related_name="member_notes",
        null=True,
        blank=True,
    )
    text = models.TextField()

    class Meta:
        verbose_name = "observação sobre integrante"
        verbose_name_plural = "observações sobre integrantes"

    def __str__(self):
        return f"{self.member} ({self.created_at:%d/%m/%Y})"
