"""UC19 — Configurar limites da equipe. RF48. Regras: RN07, RN33."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Edition
from apps.editions.rules import (
    ensure_team_limits_editable,
    ensure_team_limits_valid,
)


@transaction.atomic
def configure_team_limits(
    *,
    actor: User,
    edition: Edition,
    min_members: int,
    max_members: int,
) -> Edition:
    """Grava o mínimo e o máximo de integrantes por equipe da edição.

    Devolve a edição relida do banco; o objeto recebido não é atualizado.

    Levanta NotAdminActor se o actor não for admin, InvalidTeamLimits se os
    limites forem inválidos e TeamLimitsLocked se a edição não estiver em
    configuração.
    """
    ensure_actor_is_admin(actor)
    ensure_team_limits_valid(min_members, max_members)

    # Trava a linha e relê: a publicação pode ter acontecido depois que o chamador
    # carregou a edição, e o status do objeto recebido estaria velho.
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_team_limits_editable(edition)

    edition.min_members = min_members
    edition.max_members = max_members
    edition.save(update_fields=["min_members", "max_members", "updated_at"])
    return edition
