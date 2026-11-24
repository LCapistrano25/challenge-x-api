"""RF19, RN49 — Gravar a pontuação dos integrantes, com o período congelado."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Edition
from apps.editions.rules import ensure_edition_not_closed
from apps.projects.models import Project
from apps.results.compute import compute_points
from apps.results.exceptions import ResultsNotCalculated
from apps.results.models import ProjectResult, StudentScore
from apps.results.rules import ensure_results_not_approved


@transaction.atomic
def compute_student_points(*, actor: User, project: Project) -> list[StudentScore]:
    """Converte a nota final do projeto em pontos para cada integrante ativo.

    O período é o do primeiro cálculo; recalcular muda só os pontos. Quem deixou
    a equipe, ou todos se o projeto saiu do ranking, perde a pontuação.
    Levanta NotAdminActor, EditionClosed, ResultsAlreadyApproved,
    ResultsNotCalculated e ValidationError se o período do aluno não for aceito.
    """
    ensure_actor_is_admin(actor)
    # Trava a edição: cálculo, finalistas e homologação acontecem um de cada vez.
    edition = Edition.objects.select_for_update().get(pk=project.edition_id)
    ensure_edition_not_closed(edition)
    ensure_results_not_approved(edition)
    result = ProjectResult.objects.filter(project=project).first()
    if result is None:
        raise ResultsNotCalculated()

    stored = {s.student_id: s for s in project.student_scores.all()}
    scores = []
    if result.final_score is not None:
        now = timezone.now()
        members = project.team.members.filter(active=True).select_related("student")
        for member in members:
            score = stored.pop(member.student_id, None) or StudentScore(
                project=project, student=member.student, term=member.student.term
            )
            score.points = compute_points(result.final_score, score.term)
            score.calculated_at = now
            score.full_clean()
            score.save()
            scores.append(score)
    StudentScore.objects.filter(pk__in=[s.pk for s in stored.values()]).delete()
    return scores
