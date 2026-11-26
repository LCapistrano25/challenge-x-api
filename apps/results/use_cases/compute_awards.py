"""RF49, Art. 26, D-01 — Calcular o pódio por categoria na edição."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Edition
from apps.editions.rules import ensure_edition_not_closed
from apps.results.models import ProjectResult
from apps.results.rules import (
    ensure_has_finalists,
    ensure_results_calculated,
    ensure_results_not_approved,
)
from apps.results.selectors import compute_award_ranks


@transaction.atomic
def compute_awards(*, actor: User, edition: Edition) -> None:
    """Grava category_rank e award (1 a 3) dos finalistas; pode repetir.

    Um pódio só por categoria, na edição inteira (D-01). A ordem está em
    compute_award_ranks. Levanta NotAdminActor, EditionClosed,
    ResultsAlreadyApproved, ResultsNotCalculated e NoFinalists.
    """
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)
    ensure_results_not_approved(edition)
    ensure_results_calculated(edition)
    ensure_has_finalists(edition)

    ranks = compute_award_ranks(edition)
    now = timezone.now()
    results = ProjectResult.objects.filter(project__edition=edition)
    results.update(category_rank=None, award=None, updated_at=now)
    for result in results.filter(pk__in=list(ranks)):
        rank = ranks[result.pk]
        result.category_rank = rank
        result.award = rank if rank <= 3 else None
        result.save(update_fields=["category_rank", "award", "updated_at"])
