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


def test_nota_da_etapa_e_proporcional_aos_criterios():
    # D-02: critérios valem 10; 8 + 6 de 20 numa etapa de 3 pontos = 2,10.
    projeto = ProjectFactory()
    etapa = StageFactory(edition=projeto.edition, max_score=Decimal("3.00"))
    c1 = StageCriterionFactory(stage=etapa, max_score=Decimal("10.00"))
    c2 = StageCriterionFactory(stage=etapa, max_score=Decimal("10.00"))
    for pontos in (("8.00", "6.00"), ("10.00", "10.00")):
        avaliacao = EvaluationFactory(project=projeto, stage=etapa, finalized=True)
        EvaluationItemFactory(
            evaluation=avaliacao, stage_criterion=c1, points=Decimal(pontos[0])
        )
        EvaluationItemFactory(
            evaluation=avaliacao, stage_criterion=c2, points=Decimal(pontos[1])
        )

    nota = recalculate_stage_score(project=projeto, stage=etapa)

    # Média de 2,10 e 3,00.
    assert nota.value == Decimal("2.55")


def test_criterio_com_peso_maior_pesa_mais():
    projeto = ProjectFactory()
    etapa = StageFactory(edition=projeto.edition, max_score=Decimal("2.00"))
    leve = StageCriterionFactory(stage=etapa, max_score=Decimal("5.00"))
    pesado = StageCriterionFactory(stage=etapa, max_score=Decimal("15.00"))
    avaliacao = EvaluationFactory(project=projeto, stage=etapa, finalized=True)
    EvaluationItemFactory(evaluation=avaliacao, stage_criterion=leve, points=0)
    EvaluationItemFactory(
        evaluation=avaliacao, stage_criterion=pesado, points=Decimal("15.00")
    )

    nota = recalculate_stage_score(project=projeto, stage=etapa)

    # 15 de 20 = 75% de 2 pontos.
    assert nota.value == Decimal("1.50")
