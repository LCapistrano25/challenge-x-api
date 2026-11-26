"""UC05 — Cadastrar um desafio da edição (RF05, RN09, RN11)."""

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
def create_challenge(
    *,
    actor: User,
    edition: Edition,
    course_id: int,
    sdg_id: int,
    description: str,
    active: bool = True,
) -> Challenge:
    ensure_actor_is_admin(actor)
    # Serializa com alterações das ODS habilitadas da edição.
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)
    ensure_course_is_active(course_id)
    ensure_challenge_sdg_is_valid(edition.pk, sdg_id)
    return Challenge.objects.create(
        edition=edition,
        course_id=course_id,
        sdg_id=sdg_id,
        description=description,
        active=active,
    )
