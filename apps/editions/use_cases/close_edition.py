"""UC18 — Encerrar a edição (RF47, P-16, P-26, P-45)."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionAlreadyClosed, EditionNotPublished
from apps.editions.models import Edition
from apps.projects.enums import ProjectStatus


@transaction.atomic
def close_edition(*, actor: User, edition: Edition) -> Edition:
    """Encerra a edição de forma irreversível e conclui os projetos (P-26)."""
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    if edition.status == EditionStatus.CLOSED:
        raise EditionAlreadyClosed()
    if edition.status != EditionStatus.PUBLISHED:
        raise EditionNotPublished()

    edition.status = EditionStatus.CLOSED
    edition.closed_at = timezone.now()
    edition.save(update_fields=["status", "closed_at", "updated_at"])
    edition.projects.exclude(status=ProjectStatus.DISQUALIFIED).update(
        status=ProjectStatus.COMPLETED, updated_at=edition.closed_at
    )
    return edition
