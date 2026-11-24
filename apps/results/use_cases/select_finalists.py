"""RF15 — Escolher os finalistas da edição."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Edition
from apps.editions.rules import ensure_edition_not_closed
from apps.results.models import ProjectResult
from apps.results.rules import (
    ensure_finalists_not_evaluated,
    ensure_projects_are_ranked,
    ensure_results_calculated,
    ensure_results_not_approved,
)


@transaction.atomic
def select_finalists(*, actor: User, edition: Edition, project_ids: list[int]) -> None:
    """Deixa como finalistas exatamente os projetos enviados pelo admin.

    Levanta NotAdminActor, EditionClosed, ResultsAlreadyApproved,
    ResultsNotCalculated, FinalistAlreadyEvaluated e ValidationError se algum
    projeto não estiver no ranking da edição.
    """
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)
    ensure_results_not_approved(edition)
    ensure_results_calculated(edition)
    ensure_projects_are_ranked(edition, project_ids)
    ensure_finalists_not_evaluated(edition, project_ids)

    results = ProjectResult.objects.filter(project__edition=edition)
    for result in results:
        finalist = result.project_id in project_ids
        if result.finalist != finalist:
            result.finalist = finalist
            result.save(update_fields=["finalist", "updated_at"])
