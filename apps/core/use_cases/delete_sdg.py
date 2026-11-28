from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps.core.exceptions import SdgInUse
from apps.core.models import Sdg


@transaction.atomic
def delete_sdg(*, actor, sdg_id: int) -> None:
    """
    Exclui uma ODS.
    Regras: Apenas admins; não exclui ODS usada por desafio ou habilitada em edição.
    """
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem excluir ODS.")

    try:
        sdg = Sdg.objects.get(id=sdg_id)
    except Sdg.DoesNotExist as e:
        raise ValidationError("ODS não encontrada.") from e

    # Desafio e ODS habilitada na edição protegem a ODS (on_delete=PROTECT).
    try:
        sdg.delete()
    except ProtectedError as exc:
        raise SdgInUse() from exc
