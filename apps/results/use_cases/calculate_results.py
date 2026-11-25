"""RF15 — Calcular a nota final e o ranking por curso."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Edition
from apps.editions.rules import ensure_edition_not_closed
from apps.results.models import ProjectResult
from apps.results.rules import (
    ensure_edition_has_scored_stages,
    ensure_results_not_approved,
)
from apps.results.selectors import list_edition_standings


@transaction.atomic
def calculate_results(*, actor: User, edition: Edition) -> None:
    """Grava nota final e posição no curso dos projetos da edição.

    Recalcular preserva os finalistas ainda classificados; quem saiu do ranking
    perde a nota, a posição e a marca de finalista.
    Levanta NotAdminActor, EditionClosed, ResultsAlreadyApproved e NoScoredStages.
    """
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)
    ensure_results_not_approved(edition)
    ensure_edition_has_scored_stages(edition)

    ranked = [s for s in list_edition_standings(edition) if s.exclusion is None]
    for standing in ranked:
        ProjectResult.objects.update_or_create(
            project=standing.project,
            defaults={
                "final_score": standing.final_score,
                "course_rank": standing.course_rank,
            },
        )
    results = ProjectResult.objects.filter(project__edition=edition)
    for result in results.exclude(project__in=[s.project for s in ranked]):
        result.final_score = None
        result.course_rank = None
        result.finalist = False
        result.save()
