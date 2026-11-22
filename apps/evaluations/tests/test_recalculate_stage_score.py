from decimal import Decimal

import pytest

from apps.editions.factories import StageCriterionFactory, StageFactory
from apps.evaluations.enums import ScoreStatus
from apps.evaluations.factories import EvaluationFactory, EvaluationItemFactory
from apps.evaluations.use_cases.recalculate_stage_score import recalculate_stage_score
from apps.projects.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def avaliar(project, stage, pontos):
    avaliacao = EvaluationFactory(project=project, stage=stage, finalized=True)
    criterio = StageCriterionFactory(stage=stage, max_score=Decimal("3.00"))
    EvaluationItemFactory(
        evaluation=avaliacao, stage_criterion=criterio, points=Decimal(pontos)
    )
    return avaliacao


def test_media_das_avaliacoes_finalizadas_vira_definitiva():
    projeto = ProjectFactory()
    etapa = StageFactory(edition=projeto.edition, min_evaluations=2)
    avaliar(projeto, etapa, "2.00")
    avaliar(projeto, etapa, "1.50")

    nota = recalculate_stage_score(project=projeto, stage=etapa)

    assert nota.status == ScoreStatus.DEFINITIVE
    assert nota.value == Decimal("1.75")
    assert nota.evaluation_count == 2


def test_abaixo_do_minimo_a_nota_fica_pendente_sem_valor():
    projeto = ProjectFactory()
    etapa = StageFactory(edition=projeto.edition, min_evaluations=2)
    avaliar(projeto, etapa, "2.00")

    nota = recalculate_stage_score(project=projeto, stage=etapa)

    assert nota.status == ScoreStatus.PENDING
    assert nota.value is None
    assert nota.evaluation_count == 1


def test_rascunho_nao_entra_na_media():
    projeto = ProjectFactory()
    etapa = StageFactory(edition=projeto.edition)
    avaliar(projeto, etapa, "2.00")
    EvaluationFactory(project=projeto, stage=etapa)

    nota = recalculate_stage_score(project=projeto, stage=etapa)

    assert nota.evaluation_count == 1


def test_recalcular_atualiza_a_mesma_nota():
    projeto = ProjectFactory()
    etapa = StageFactory(edition=projeto.edition)
    avaliar(projeto, etapa, "1.00")
    primeira = recalculate_stage_score(project=projeto, stage=etapa)
    avaliar(projeto, etapa, "2.00")

    segunda = recalculate_stage_score(project=projeto, stage=etapa)

    assert segunda.pk == primeira.pk
    assert segunda.value == Decimal("1.50")
