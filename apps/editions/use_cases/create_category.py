"""UC20 — Cadastrar categoria da edição (RF49)."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import translate_category_name_conflict
from apps.editions.models import Category, Edition
from apps.editions.rules import ensure_edition_not_closed


@transaction.atomic
def create_category(
    *,
    actor: User,
    edition: Edition,
    name: str,
    description: str | None = None,
    active: bool = True,
) -> Category:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)
    with translate_category_name_conflict():
        return Category.objects.create(
            edition=edition, name=name, description=description or "", active=active
        )
