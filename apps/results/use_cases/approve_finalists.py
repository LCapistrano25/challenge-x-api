"""UC15, RF15 — Homologar os finalistas e o resultado da edição."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Edition
from apps.editions.rules import ensure_edition_not_closed
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.results.models import ProjectResult
from apps.results.rules import (
    ensure_awards_calculated,
    ensure_has_finalists,
    ensure_no_pending_scores,
    ensure_results_calculated,
    ensure_results_not_approved,
    ensure_results_up_to_date,
)
from apps.results.selectors import list_edition_standings


@transaction.atomic
def approve_finalists(*, actor: User, edition: Edition) -> None:
    """Grava a homologação em todos os projetos classificados da edição.

    Vem por último: depois das notas, dos finalistas e do pódio (D-01). Não
    recalcula: se as notas mudaram depois do cálculo, recusa. Também recusa
    enquanto houver nota de etapa pendente (decisão de 25/11, #230).
    Levanta NotAdminActor, EditionClosed, ResultsAlreadyApproved,
    ResultsNotCalculated, NoFinalists, PendingScores, AwardsNotCalculated e
    ResultsOutdated.
    """
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)
    ensure_results_not_approved(edition)
    ensure_results_calculated(edition)
    ensure_has_finalists(edition)
    standings = list_edition_standings(edition)
    ensure_no_pending_scores(standings)
    ensure_awards_calculated(edition)
    ensure_results_up_to_date(
        edition,
        {
            s.project.pk: (s.final_score, s.course_rank)
            for s in standings
            if s.exclusion is None
        },
    )
    now = timezone.now()
    ProjectResult.objects.filter(
        project__edition=edition, final_score__isnull=False
    ).update(approved_at=now, updated_at=now)
    _notify_results_approved(edition=edition)


def _notify_results_approved(*, edition: Edition) -> None:
    results = ProjectResult.objects.filter(
        project__edition=edition,
        final_score__isnull=False,
    ).select_related("project__team")
    for result in results:
        project = result.project
        if result.award:
            title = "Projeto premiado!"
            message = (
                f"O projeto {project.title} ficou em {result.award}º lugar "
                "na sua categoria."
            )
        elif result.finalist:
            title = "Resultado da edição homologado"
            message = f"O projeto {project.title} foi finalista da edição."
        else:
            title = "Resultado da edição publicado"
            message = (
                f"O resultado do projeto {project.title} foi homologado "
                f"({result.course_rank}º lugar no curso)."
            )

        members = project.team.members.filter(active=True).select_related(
            "student__user"
        )
        for member in members:
            create_notification(
                user=member.student.user,
                notification_type=NotificationType.RESULT,
                title=title,
                message=message,
                link=f"/projects/{project.id}/scores",
            )
