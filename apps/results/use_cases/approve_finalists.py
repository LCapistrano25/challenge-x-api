"""UC15, RF15 — Homologar os finalistas e o resultado da edição."""

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
    ensure_results_up_to_date,
)
from apps.results.selectors import list_edition_standings


@transaction.atomic
def approve_finalists(*, actor: User, edition: Edition) -> None:
    """Grava a homologação em todos os projetos classificados da edição.

    Não recalcula: se as notas mudaram depois do cálculo, recusa.
    Levanta NotAdminActor, EditionClosed, ResultsAlreadyApproved,
    ResultsNotCalculated, NoFinalists e ResultsOutdated.
    """
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)
    ensure_results_not_approved(edition)
    ensure_results_calculated(edition)
    ensure_has_finalists(edition)
    ensure_results_up_to_date(
        edition,
        {
            s.project.pk: (s.final_score, s.course_rank)
            for s in list_edition_standings(edition)
            if s.exclusion is None
        },
    )
    now = timezone.now()
    ProjectResult.objects.filter(
        project__edition=edition, final_score__isnull=False
    ).update(approved_at=now, updated_at=now)
