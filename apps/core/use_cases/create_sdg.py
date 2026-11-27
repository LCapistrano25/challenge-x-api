from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.exceptions import SdgNumberTaken
from apps.core.models import Sdg


@transaction.atomic
def create_sdg(
    *,
    actor,
    number: int,
    title: str,
    description: str | None = "",
    icon: str | None = "",
    active: bool = True,
) -> Sdg:
    """
    Cadastra uma nova ODS.
    Regras: Admin, número entre 1 e 17, número único.
    """
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem cadastrar ODS.")

    if not (1 <= number <= 17):
        raise ValidationError("O número da ODS deve estar entre 1 e 17.")

    try:
        sdg = Sdg.objects.create(
            number=number,
            title=title,
            description=description or "",
            icon=icon or "",
            active=active,
        )
        return sdg
    except IntegrityError as e:
        raise SdgNumberTaken() from e
