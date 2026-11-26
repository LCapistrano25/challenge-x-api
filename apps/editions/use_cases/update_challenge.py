"""UC05 — Atualizar um desafio da edição (RF05, RN09, RN11)."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Challenge, Edition
from apps.editions.rules import (
    ensure_challenge_sdg_is_valid,
    ensure_course_is_active,
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

    if course_id is not None:
        ensure_course_is_active(course_id)
    if sdg_id is not None:
        ensure_challenge_sdg_is_valid(edition.pk, sdg_id)

    updates = {
        "course_id": course_id,
        "sdg_id": sdg_id,
        "description": description,
        "active": active,
    }
    updates = {field: value for field, value in updates.items() if value is not None}
    for field, value in updates.items():
        setattr(challenge, field, value)
    if updates:
        challenge.save(update_fields=[*updates, "updated_at"])
    return challenge
