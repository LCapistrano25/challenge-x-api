import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class NotificationType(models.TextChoices):
    SYSTEM = "SYSTEM", "Sistema"
    TEAM = "TEAM", "Equipe"
    PROJECT = "PROJECT", "Projeto"
    DELIVERABLE = "DELIVERABLE", "Entrega"
    EVALUATION = "EVALUATION", "Avaliação"
    RESULT = "RESULT", "Resultado"
    CERTIFICATE = "CERTIFICATE", "Certificado"


class Notification(TimeStampedModel):
    """Notificação exibida no painel do usuário."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "notificação"
        verbose_name_plural = "notificações"

    def __str__(self):
        return f"{self.title} - {self.user.email}"
