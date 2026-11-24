from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from apps.editions.enums import StageKind
from apps.editions.models import Criterion, Stage
from apps.evaluations.enums import EvaluationStatus, ScoreStatus
from apps.evaluations.models import EvaluationItem, StageScore
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.results.compute import CENT, RankEntry, compute_course_ranks
from apps.results.enums import ResultExclusionReason
from apps.teams.enums import TeamStatus


@dataclass(frozen=True)
class Standing:
    """Situação atual de um projeto no ranking; `exclusion` diz por que ficou fora."""

    project: Project
    final_score: Decimal | None
    course_rank: int | None
    exclusion: str | None


def list_edition_standings(edition) -> list[Standing]:
    """Nota final e posição no curso de cada projeto da edição, sem gravar (RF15).

    A nota é a soma das etapas de entrega pontuadas, todas definitivas ou zeradas
    por falta de entrega. Equipe desfeita não aparece.
    """
    projects = list(
        Project.objects.filter(edition=edition)
        .exclude(team__status=TeamStatus.DISBANDED)
        .select_related("team", "challenge__course", "category")
        .order_by("pk")
    )
    stage_ids = list(
        Stage.objects.filter(
            edition=edition, kind=StageKind.SUBMISSION, scored=True
        ).values_list("pk", flat=True)
    )
    scores = defaultdict(list)
    for project_id, value in StageScore.objects.filter(
        project__in=projects,
        stage_id__in=stage_ids,
        status__in=[ScoreStatus.DEFINITIVE, ScoreStatus.ZERO_NO_SUBMISSION],
    ).values_list("project_id", "value"):
        scores[project_id].append(value)

    totals, exclusions = {}, {}
    for project in projects:
        if (
            project.team.status == TeamStatus.DISQUALIFIED
            or project.status == ProjectStatus.DISQUALIFIED
        ):
            exclusions[project.pk] = ResultExclusionReason.DISQUALIFIED
        elif project.challenge_id is None:
            exclusions[project.pk] = ResultExclusionReason.NO_CHALLENGE
        elif not stage_ids or len(scores[project.pk]) < len(stage_ids):
            exclusions[project.pk] = ResultExclusionReason.PENDING_SCORE
        else:
            totals[project.pk] = sum(scores[project.pk], Decimal("0.00"))

    tiebreaks = _tiebreak_scores(edition, list(totals), stage_ids)
    ranks = compute_course_ranks(
        [
            RankEntry(
                project.pk,
                project.challenge.course_id,
                totals[project.pk],
                tiebreaks[project.pk],
            )
            for project in projects
            if project.pk in totals
        ]
    )
    return [
        Standing(
            project=project,
            final_score=totals.get(project.pk),
            course_rank=ranks.get(project.pk),
            exclusion=exclusions.get(project.pk),
        )
        for project in projects
    ]


def _tiebreak_scores(edition, project_ids, stage_ids) -> dict[int, tuple]:
    """Pontos de cada critério de desempate, na ordem de `tiebreak_order`.

    Por etapa, média das avaliações finalizadas; entre etapas, soma.
    """
    criterion_ids = list(
        Criterion.objects.filter(edition=edition, tiebreak_order__isnull=False)
        .order_by("tiebreak_order")
        .values_list("pk", flat=True)
    )
    points = defaultdict(list)
    for project_id, stage_id, criterion_id, value in EvaluationItem.objects.filter(
        evaluation__project_id__in=project_ids,
        evaluation__stage_id__in=stage_ids,
        evaluation__status=EvaluationStatus.FINALIZED,
        stage_criterion__criterion_id__in=criterion_ids,
    ).values_list(
        "evaluation__project_id",
        "evaluation__stage_id",
        "stage_criterion__criterion_id",
        "points",
    ):
        points[project_id, stage_id, criterion_id].append(value)

    totals = defaultdict(Decimal)
    for (project_id, _, criterion_id), values in points.items():
        average = (sum(values) / len(values)).quantize(CENT, rounding=ROUND_HALF_UP)
        totals[project_id, criterion_id] += average
    return {
        project_id: tuple(
            totals.get((project_id, criterion_id), Decimal(0))
            for criterion_id in criterion_ids
        )
        for project_id in project_ids
    }
