from django.db import models


class EditionStatus(models.TextChoices):
    SETUP = "SETUP", "Em configuração"
    PUBLISHED = "PUBLISHED", "Publicada"
    CLOSED = "CLOSED", "Encerrada"


class StageKind(models.TextChoices):
    # FORMATION delimita o prazo de formação de equipes; FINAL é a dos avaliadores.
    FORMATION = "FORMATION", "Formação de equipes"
    SUBMISSION = "SUBMISSION", "Entrega"
    FINAL = "FINAL", "Apresentação final"


class FieldKind(models.TextChoices):
    LINK = "LINK", "Link"
    FILE = "FILE", "Arquivo"
    # Preenchidos no sistema, com modelo fixo no código (RF07, RF31).
    CANVAS = "CANVAS", "Business Model Canvas"
    SWOT = "SWOT", "Matriz SWOT"
