"""UC18 — Cadastrar edição. RF47. Regras: RN05."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionAlreadyExists
from apps.editions.models import Edition
from apps.editions.rules import (
    ensure_actor_is_admin,
    ensure_edition_identification_is_free,
)


@transaction.atomic
def create_edition(
    *,
    actor: User,
    year: int,
    semester: int,
    name: str = "",
) -> Edition:
    """Cadastra a edição em configuração, com os limites padrão de 3 a 5.

    Levanta NotAdminActor se o actor não for admin, ValidationError se o semestre
    não for 1 ou 2 e EditionAlreadyExists se o ano e o semestre já estiverem em uso.
    """
    ensure_actor_is_admin(actor)
    if semester not in (1, 2):
        raise ValidationError({"semester": "O semestre deve ser 1 ou 2."})
    ensure_edition_identification_is_free(year, semester)

    try:
        # Savepoint próprio: o IntegrityError não deixa a transação inutilizável.
        with transaction.atomic():
            return Edition.objects.create(
                year=year, semester=semester, name=name, status=EditionStatus.SETUP
            )
    except IntegrityError:
        # Duas requisições passam pela checagem acima; o banco desempata. Se a
        # edição agora existe, a causa é a unicidade; senão o erro é outro.
        if Edition.objects.filter(year=year, semester=semester).exists():
            raise EditionAlreadyExists() from None
        raise
