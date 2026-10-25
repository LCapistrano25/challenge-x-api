from django.db import models


class EvaluationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Rascunho"
    FINALIZED = "FINALIZED", "Finalizada"


class ScoreStatus(models.TextChoices):
    # Pendente até atingir o mínimo de avaliações da etapa (RN25).
    PENDING = "PENDING", "Pendente"
    DEFINITIVE = "DEFINITIVE", "Definitiva"
    # Zero automático por falta de entrega (RN24).
    ZERO_NO_SUBMISSION = "ZERO_NO_SUBMISSION", "Zero sem entrega"


class QuestionKind(models.TextChoices):
    SCORE = "SCORE", "Nota"
    CONCEPT = "CONCEPT", "Conceito"
    TEXT = "TEXT", "Texto"


class FinalEvaluationStatus(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    EVALUATED = "EVALUATED", "Avaliado"
