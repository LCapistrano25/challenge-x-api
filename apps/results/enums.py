from django.db import models


class CertificateKind(models.TextChoices):
    # Incompleto em relação ao RF17 (P-34).
    PARTICIPATION = "PARTICIPATION", "Participação"
    FINALIST = "FINALIST", "Finalista"
    AWARD = "AWARD", "Premiação"


class ResultExclusionReason(models.TextChoices):
    # Por que o projeto ficou fora do ranking (RF15); nada é gravado.
    DISQUALIFIED = "DISQUALIFIED", "Desclassificado"
    NO_CHALLENGE = "NO_CHALLENGE", "Sem desafio"
    PENDING_SCORE = "PENDING_SCORE", "Nota pendente"
