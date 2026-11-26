"""UC20 — Excluir uma categoria sem uso (RF49)."""

from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import CategoryInUse
from apps.editions.models import Category, Edition
from apps.editions.rules import ensure_edition_not_closed
from apps.editions.selectors import get_locked_category


@transaction.atomic
def delete_category(*, actor: User, category: Category) -> None:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=category.edition_id)
    ensure_edition_not_closed(edition)
    category = get_locked_category(category.pk)
    try:
        category.delete()
    except ProtectedError as error:
        raise CategoryInUse() from error
