from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import Sdg


@transaction.atomic
def update_sdg(
    *,
    actor,
    sdg_id: int,
    title: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    active: bool | None = None,
) -> Sdg:
    """
    Atualiza os dados de uma ODS.
    Regra: Apenas administradores. O número não é editável.
    """
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem atualizar ODS.")

    try:
        sdg = Sdg.objects.get(id=sdg_id)
    except Sdg.DoesNotExist as e:
        raise ValidationError("ODS não encontrada.") from e

    if title is not None:
        sdg.title = title
    if description is not None:
        sdg.description = description
    if icon is not None:
        sdg.icon = icon
    if active is not None:
        sdg.active = active

    sdg.save()
    return sdg
