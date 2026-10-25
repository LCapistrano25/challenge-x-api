from django.db import models


class TeamStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Ativa"
    DISQUALIFIED = "DISQUALIFIED", "Desclassificada"


class TeamSituation(models.TextChoices):
    # Apurada no encerramento do prazo de formação (RF51).
    COMPLETE = "COMPLETE", "Completa"
    INCOMPLETE = "INCOMPLETE", "Incompleta"
    REQUIREMENTS_NOT_MET = "REQUIREMENTS_NOT_MET", "Requisitos não atendidos"


class MemberRole(models.TextChoices):
    LEADER = "LEADER", "Líder"
    MEMBER = "MEMBER", "Membro"


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    ACCEPTED = "ACCEPTED", "Aceito"
    DECLINED = "DECLINED", "Recusado"
    CANCELLED = "CANCELLED", "Cancelado"


class RequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    APPROVED = "APPROVED", "Aprovada"
    REJECTED = "REJECTED", "Recusada"
    CANCELLED = "CANCELLED", "Cancelada"
