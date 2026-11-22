from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import Sdg


@transaction.atomic
def delete_sdg(*, actor, sdg_id: int) -> None:
    """
    Exclui uma ODS.
    Regras: Apenas admins e não exclui se estiver usada em um desafio.
    """
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem excluir ODS.")

    try:
        sdg = Sdg.objects.get(id=sdg_id)
    except Sdg.DoesNotExist as e:
        raise ValidationError("ODS não encontrada.") from e

    # Verifica se a ODS está vinculada a algum desafio
    # Assumindo que a relação reversa padrão do Django seja challenge_set
    if hasattr(sdg, "challenge_set") and sdg.challenge_set.exists():
        raise ValidationError(
            "Não é possível excluir esta ODS, pois está vinculada a um desafio."
        )

    sdg.delete()
