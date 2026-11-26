"""UC05 — Atualizar um desafio da edição (RF05, RN09, RN11)."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Challenge, Edition
from apps.editions.rules import (
    ensure_challenge_catalog_is_valid,
    ensure_edition_not_closed,
)


@transaction.atomic
def update_challenge(
    *,
    actor: User,
    challenge: Challenge,
    course_id: int | None = None,
    sdg_id: int | None = None,
    description: str | None = None,
    active: bool | None = None,
) -> Challenge:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=challenge.edition_id)
    ensure_edition_not_closed(edition)
    challenge = Challenge.objects.select_for_update().get(pk=challenge.pk)

    updates = {
        "course_id": course_id,
        "sdg_id": sdg_id,
        "description": description,
        "active": active,
    }
    updates = {field: value for field, value in updates.items() if value is not None}
    for field, value in updates.items():
        setattr(challenge, field, value)
    ensure_challenge_catalog_is_valid(edition.pk, challenge.course_id, challenge.sdg_id)
    if updates:
        challenge.save(update_fields=[*updates, "updated_at"])
    return challenge
