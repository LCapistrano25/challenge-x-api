"""UC06 — Cadastrar critério de avaliação (RF06)."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import translate_criterion_conflict
from apps.editions.models import Criterion, Edition
from apps.editions.rules import (
    ensure_criterion_values_are_unique,
    ensure_criterion_values_are_valid,
    ensure_edition_not_closed,
)


@transaction.atomic
def create_criterion(
    *,
    actor: User,
    edition: Edition,
    name: str,
    rubric: str | None = None,
    tiebreak_order: int | None = None,
) -> Criterion:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)
    ensure_criterion_values_are_valid(name=name, tiebreak_order=tiebreak_order)
    name = name.strip()
    ensure_criterion_values_are_unique(
        edition_id=edition.pk, name=name, tiebreak_order=tiebreak_order
    )
    with translate_criterion_conflict(), transaction.atomic():
        return Criterion.objects.create(
            edition=edition,
            name=name,
            rubric=rubric or "",
            tiebreak_order=tiebreak_order,
        )
