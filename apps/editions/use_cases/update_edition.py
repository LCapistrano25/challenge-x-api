"""UC18 e UC19 — Atualizar nome e limites da edição. RF47, RF48. Regras: RN07, RN33."""

from django.db import transaction

from apps.accounts.models import User
from apps.editions.models import Edition
from apps.editions.rules import (
    ensure_actor_is_admin,
    ensure_edition_not_closed,
    ensure_team_limits_editable,
    ensure_team_limits_valid,
)

# Distingue "não informado" (não mexe) de None (limpa o nome).
UNSET = object()


@transaction.atomic
def update_edition(
    *,
    actor: User,
    edition: Edition,
    name: str | None = UNSET,
    min_members: int = UNSET,
    max_members: int = UNSET,
) -> Edition:
    """Atualiza só o que veio informado; campo ausente não é tocado.

    Encerrada: nada muda. Publicada: só o nome (RF48). Em configuração: nome e
    limites. Limite informado sozinho completa o outro com o valor atual do banco.
    Qualquer recusa deixa a edição como estava, sem alteração parcial.
    """
    ensure_actor_is_admin(actor)
    # A linha fica travada até o fim: estado e limites vêm do banco, não do
    # objeto recebido, que pode estar velho.
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)

    changed = []
    if min_members is not UNSET or max_members is not UNSET:
        new_min = edition.min_members if min_members is UNSET else min_members
        new_max = edition.max_members if max_members is UNSET else max_members
        ensure_team_limits_editable(edition)
        ensure_team_limits_valid(new_min, new_max)
        edition.min_members = new_min
        edition.max_members = new_max
        changed += ["min_members", "max_members"]
    if name is not UNSET:
        edition.name = name or ""
        changed.append("name")

    if changed:
        edition.save(update_fields=[*changed, "updated_at"])
    return edition
