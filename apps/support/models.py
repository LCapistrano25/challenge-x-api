import uuid

from django.conf import settings
from django.db import models

from apps.support.enums import SupportTicketPriority, SupportTicketStatus


class SupportTicket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
        verbose_name="solicitante",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
        verbose_name="responsável",
    )
    title = models.CharField("título", max_length=150)
    description = models.TextField("descrição")
    status = models.CharField(
        "status",
        max_length=20,
        choices=SupportTicketStatus.choices,
        default=SupportTicketStatus.OPEN,
    )
    priority = models.CharField(
        "prioridade",
        max_length=20,
        choices=SupportTicketPriority.choices,
        default=SupportTicketPriority.MEDIUM,
    )
    support_response = models.TextField("resposta do suporte", null=True, blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)
    resolved_at = models.DateTimeField("resolvido em", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "chamado de suporte"
        verbose_name_plural = "chamados de suporte"
        indexes = [
            models.Index(fields=["requester", "-created_at"]),
            models.Index(fields=["status", "priority", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"
