"""UC20 — Atualizar uma categoria da edição (RF49)."""

from typing import TypedDict, Unpack

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import translate_category_name_conflict
from apps.editions.models import Category, Edition
from apps.editions.rules import ensure_edition_not_closed
from apps.editions.selectors import get_locked_category


class _CategoryChanges(TypedDict, total=False):
    name: str
    description: str | None
    active: bool


@transaction.atomic
def update_category(
    *, actor: User, category: Category, **changes: Unpack[_CategoryChanges]
) -> Category:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=category.edition_id)
    ensure_edition_not_closed(edition)
    category = get_locked_category(category.pk)

    fields = []
    if "name" in changes:
        category.name = changes["name"]
        fields.append("name")
    if "description" in changes:
        category.description = changes["description"] or ""
        fields.append("description")
    if "active" in changes:
        category.active = changes["active"]
        fields.append("active")
    if fields:
        with translate_category_name_conflict():
            category.save(update_fields=[*fields, "updated_at"])
    return category
