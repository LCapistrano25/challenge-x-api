from django.db import models


class ProjectStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "Em andamento"
    COMPLETED = "COMPLETED", "Concluído"
    DISQUALIFIED = "DISQUALIFIED", "Desclassificado"
