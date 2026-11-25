from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.editions.factories import StageFactory
from apps.evaluations.factories import FinalEvaluationFactory
from apps.results import rules
from apps.results.exceptions import (
    FinalistAlreadyEvaluated,
    NoFinalists,
    NoScoredStages,
    ResultsAlreadyApproved,
    ResultsNotCalculated,
    ResultsOutdated,
)
from apps.results.factories import ProjectResultFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_result(make_project):
    def make(final_score="5.00", course_rank=1, **kwargs):
        return ProjectResultFactory(
            project=make_project(),
            final_score=None if final_score is None else Decimal(final_score),
            course_rank=course_rank,
            **kwargs,
        )

    return make


def test_etapa_pontuada_passa(edition, stages):
    rules.ensure_edition_has_scored_stages(edition)


def test_etapa_pontuada_barra(edition):
    StageFactory(edition=edition, formation=True)

    with pytest.raises(NoScoredStages):
        rules.ensure_edition_has_scored_stages(edition)


def test_nao_homologado_passa_mesmo_com_outra_edicao_homologada(edition, make_result):
    make_result()
    ProjectResultFactory(approved_at=timezone.now())

    rules.ensure_results_not_approved(edition)


def test_homologado_barra(edition, make_result):
    make_result(approved_at=timezone.now())

    with pytest.raises(ResultsAlreadyApproved):
        rules.ensure_results_not_approved(edition)


def test_calculado_passa(edition, make_result):
    make_result()

    rules.ensure_results_calculated(edition)


def test_calculado_barra_sem_nota_ou_so_de_outra_edicao(edition, make_result):
    make_result(final_score=None, course_rank=None)
    ProjectResultFactory()

    with pytest.raises(ResultsNotCalculated):
        rules.ensure_results_calculated(edition)


def test_classificados_passam(edition, make_result):
    ids = [make_result().project_id, make_result().project_id]

    rules.ensure_projects_are_ranked(edition, ids)


@pytest.mark.parametrize("case", ["inexistente", "outra_edicao", "sem_nota"])
def test_fora_do_ranking_barra(edition, make_result, case):
    ranked = make_result().project_id
    other = {
        "inexistente": lambda: 999999,
        "outra_edicao": lambda: ProjectResultFactory().project_id,
        "sem_nota": lambda: make_result(final_score=None, course_rank=None).project_id,
    }[case]()

    with pytest.raises(ValidationError) as error:
        rules.ensure_projects_are_ranked(edition, [ranked, other])

    assert "project_ids" in error.value.message_dict


def test_manter_finalista_avaliado_passa(edition, make_result):
    result = make_result(finalist=True)
    FinalEvaluationFactory(project=result.project)

    rules.ensure_finalists_not_evaluated(edition, [result.project_id])


def test_retirar_finalista_sem_avaliacao_passa(edition, make_result):
    make_result(finalist=True)

    rules.ensure_finalists_not_evaluated(edition, [])


def test_retirar_finalista_avaliado_barra(edition, make_result):
    result = make_result(finalist=True)
    FinalEvaluationFactory(project=result.project)

    with pytest.raises(FinalistAlreadyEvaluated):
        rules.ensure_finalists_not_evaluated(edition, [])


def test_com_finalista_passa(edition, make_result):
    make_result(finalist=True)

    rules.ensure_has_finalists(edition)


def test_sem_finalista_barra(edition, make_result):
    make_result()
    ProjectResultFactory(finalist=True)

    with pytest.raises(NoFinalists):
        rules.ensure_has_finalists(edition)


def test_resultado_em_dia_passa(edition, make_result):
    result = make_result()
    make_result(final_score=None, course_rank=None)

    rules.ensure_results_up_to_date(edition, {result.project_id: (Decimal("5.00"), 1)})


@pytest.mark.parametrize("case", ["nota", "posicao", "a_mais", "a_menos"])
def test_resultado_defasado_barra(edition, make_result, case):
    project_id = make_result().project_id
    expected = {
        "nota": {project_id: (Decimal("6.00"), 1)},
        "posicao": {project_id: (Decimal("5.00"), 2)},
        "a_mais": {
            project_id: (Decimal("5.00"), 1),
            999999: (Decimal("4.00"), 2),
        },
        "a_menos": {},
    }[case]

    with pytest.raises(ResultsOutdated):
        rules.ensure_results_up_to_date(edition, expected)
