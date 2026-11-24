from django.db import models


class ProjectStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "Em andamento"
    COMPLETED = "COMPLETED", "Concluído"
    DISQUALIFIED = "DISQUALIFIED", "Desclassificado"


class DeliveryStatus(models.TextChoices):
    # Derivado das versões e do prazo da equipe; nada é gravado (P-27).
    NOT_SUBMITTED = "NOT_SUBMITTED", "Não enviada"
    SUBMITTED = "SUBMITTED", "Enviada"
    NOT_DELIVERED = "NOT_DELIVERED", "Não entregue"


class PhaseStatus(models.TextChoices):
    UPCOMING = "UPCOMING", "Em breve"
    OPEN = "OPEN", "Aberta"
    FINISHED = "FINISHED", "Encerrada"
