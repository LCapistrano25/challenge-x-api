from django.apps import apps
from django.core.exceptions import ValidationError

from apps.results.exceptions import (
    FinalistAlreadyEvaluated,
    NoFinalists,
    NoScoredStages,
    ResultsAlreadyApproved,
    ResultsNotCalculated,
    ResultsOutdated,
)

# Os models importam estas regras; por isso elas pegam os models pelo registro
# do Django (como a FK por string), sem import que fecharia o ciclo.


def ensure_edition_has_scored_stages(edition) -> None:
    """A nota final soma as etapas de entrega pontuadas; sem elas não há cálculo."""
    stages = apps.get_model("editions", "Stage").objects
    if not stages.filter(edition=edition, kind="SUBMISSION", scored=True).exists():
        raise NoScoredStages()


def ensure_results_not_approved(edition) -> None:
    """Resultado homologado não muda (RF15)."""
    if _results(edition).filter(approved_at__isnull=False).exists():
        raise ResultsAlreadyApproved()


def ensure_results_calculated(edition) -> None:
    """Finalistas e homologação partem das notas calculadas (RF15)."""
    if not _ranked(edition).exists():
        raise ResultsNotCalculated()


def ensure_projects_are_ranked(edition, project_ids) -> None:
    """Só projeto classificado da edição pode ser finalista (RF15)."""
    ids = set(project_ids)
    if _ranked(edition).filter(project_id__in=ids).count() != len(ids):
        raise ValidationError(
            {"project_ids": "Há projeto fora do ranking desta edição."}
        )


def ensure_finalists_not_evaluated(edition, project_ids) -> None:
    """Finalista que já recebeu avaliação final não sai da lista."""
    removed = (
        _results(edition).filter(finalist=True).exclude(project_id__in=project_ids)
    )
    evaluations = apps.get_model("evaluations", "FinalEvaluation").objects
    if evaluations.filter(project_id__in=removed.values("project_id")).exists():
        raise FinalistAlreadyEvaluated()


def ensure_has_finalists(edition) -> None:
    """Não se homologa resultado sem finalista (UC15)."""
    if not _ranked(edition).filter(finalist=True).exists():
        raise NoFinalists()


def ensure_results_up_to_date(edition, expected) -> None:
    """O gravado confere com as notas atuais: {projeto: (nota final, posição)}."""
    stored = {
        project_id: (final_score, course_rank)
        for project_id, final_score, course_rank in _ranked(edition).values_list(
            "project_id", "final_score", "course_rank"
        )
    }
    if stored != expected:
        raise ResultsOutdated()


def _results(edition):
    results = apps.get_model("results", "ProjectResult").objects
    return results.filter(project__edition=edition)


def _ranked(edition):
    return _results(edition).filter(final_score__isnull=False)
