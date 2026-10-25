from django.db import models


class CertificateKind(models.TextChoices):
    # Incompleto em relação ao RF17 (P-34).
    PARTICIPATION = "PARTICIPATION", "Participação"
    FINALIST = "FINALIST", "Finalista"
    AWARD = "AWARD", "Premiação"
