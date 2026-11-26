from django.db import models


class SupportTicketStatus(models.TextChoices):
    OPEN = "OPEN", "Aberto"
    IN_PROGRESS = "IN_PROGRESS", "Em análise"
    WAITING_USER = "WAITING_USER", "Aguardando usuário"
    RESOLVED = "RESOLVED", "Atendido"
    CLOSED = "CLOSED", "Recusado"


class SupportTicketPriority(models.TextChoices):
    LOW = "LOW", "Baixa"
    MEDIUM = "MEDIUM", "Média"
    HIGH = "HIGH", "Alta"
    URGENT = "URGENT", "Urgente"
