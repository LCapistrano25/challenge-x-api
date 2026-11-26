"""UC06 — Atualiza um critério de avaliação da edição (RF06)."""

from typing import TypedDict, Unpack

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import translate_criterion_conflict
from apps.editions.models import Criterion, Edition
from apps.editions.rules import (
    ensure_criterion_has_no_evaluations,
    ensure_criterion_values_are_unique,
    ensure_criterion_values_are_valid,
    ensure_edition_not_closed,
)
from apps.editions.selectors import get_locked_criterion


class _CriterionChanges(TypedDict, total=False):
    name: str
    rubric: str | None
    tiebreak_order: int | None


@transaction.atomic
def update_criterion(
    *, actor: User, criterion: Criterion, **changes: Unpack[_CriterionChanges]
) -> Criterion:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=criterion.edition_id)
    ensure_edition_not_closed(edition)
    criterion = get_locked_criterion(criterion.pk)
    ensure_criterion_has_no_evaluations(criterion.pk)

    name = changes.get("name", criterion.name)
    tiebreak_order = changes.get("tiebreak_order", criterion.tiebreak_order)
    ensure_criterion_values_are_valid(name=name, tiebreak_order=tiebreak_order)
    if "name" in changes:
        name = name.strip()
    ensure_criterion_values_are_unique(
        edition_id=edition.pk,
        name=name,
        tiebreak_order=tiebreak_order,
        criterion_id=criterion.pk,
    )
    if changes:
        criterion.name = name
        criterion.tiebreak_order = tiebreak_order
        if "rubric" in changes:
            criterion.rubric = changes["rubric"] or ""
        with translate_criterion_conflict(), transaction.atomic():
            criterion.save(update_fields=[*changes, "updated_at"])
    return criterion
