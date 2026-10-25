import pytest

from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    CriterionFactory,
    EditionFactory,
    EditionReviewerFactory,
    EditionSdgFactory,
    StageCriterionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "factory",
    [
        EditionFactory,
        EditionSdgFactory,
        CategoryFactory,
        ChallengeFactory,
        StageFactory,
        StageSubmissionFieldFactory,
        CriterionFactory,
        StageCriterionFactory,
        EditionReviewerFactory,
    ],
)
def test_factory_gera_registro_valido(factory):
    factory().full_clean()


def test_criterio_da_etapa_nasce_na_mesma_edicao():
    vinculo = StageCriterionFactory()
    assert vinculo.criterion.edition_id == vinculo.stage.edition_id


def test_etapa_de_formacao_sem_pontuacao():
    etapa = StageFactory(formation=True)
    assert etapa.max_score is None and not etapa.scored
