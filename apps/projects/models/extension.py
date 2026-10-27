from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.core.models import TimeStampedModel
from apps.projects.rules import (
    ensure_extension_after_stage_end,
    ensure_stage_in_project_edition,
)


class DeadlineExtension(TimeStampedModel):
    """Prorrogação do prazo de entrega para uma equipe numa etapa (RF14, P-21).

    É o próprio histórico do ajuste: o admin cria e ninguém altera nem apaga.
    """

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="deadline_extensions"
    )
    stage = models.ForeignKey(
        "editions.Stage", on_delete=models.PROTECT, related_name="deadline_extensions"
    )
    ends_at = models.DateTimeField()
    reason = models.TextField()
    granted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="granted_extensions",
        limit_choices_to={"role": UserRole.ADMIN},
    )
    granted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "prorrogação de prazo"
        verbose_name_plural = "prorrogações de prazo"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "stage"], name="unique_extension_per_stage"
            ),
            models.CheckConstraint(
                condition=~Q(reason=""), name="deadline_extension_has_reason"
            ),
        ]

    def clean(self):
        if self.project_id and self.stage_id and self.ends_at:
            ensure_stage_in_project_edition(self)
            ensure_extension_after_stage_end(self)

    def __str__(self):
        return f"{self.project} — {self.stage}: até {self.ends_at:%d/%m/%Y %H:%M}"
