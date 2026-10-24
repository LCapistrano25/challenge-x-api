from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    STUDENT = "STUDENT", "Acadêmico"
    TEACHER = "TEACHER", "Professor"
    EXTERNAL_REVIEWER = "EXTERNAL_REVIEWER", "Avaliador Externo"
