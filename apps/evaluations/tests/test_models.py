from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.factories import ExternalReviewerFactory
from apps.editions.factories import EditionFactory, StageCriterionFactory, StageFactory
from apps.evaluations.enums import (
    EvaluationStatus,
    FinalEvaluationStatus,
    QuestionKind,
    ScoreStatus,
)
from apps.evaluations.factories import (
    EvaluationFactory,
    EvaluationItemFactory,
    FinalAnswerFactory,
    FinalEvaluationFactory,
    FinalFormFactory,
    FinalQuestionFactory,
    StageScoreFactory,
)
from apps.evaluations.models import (
    Evaluation,
    EvaluationItem,
    FinalAnswer,
    FinalEvaluation,
)

pytestmark = pytest.mark.django_db


# Critérios de pronto da issue BM6


def test_professor_avalia_o_projeto_uma_vez_por_etapa():
    avaliacao = EvaluationFactory()
    with pytest.raises(IntegrityError):
        EvaluationFactory(
            project=avaliacao.project,
            stage=avaliacao.stage,
            teacher=avaliacao.teacher,
        )


def test_uma_nota_por_criterio_na_avaliacao():
    item = EvaluationItemFactory()
    with pytest.raises(IntegrityError):
        EvaluationItemFactory(
            evaluation=item.evaluation, stage_criterion=item.stage_criterion
        )


# Avaliação do professor


def test_outro_professor_avalia_o_mesmo_projeto_e_etapa():
    avaliacao = EvaluationFactory()
    assert EvaluationFactory(project=avaliacao.project, stage=avaliacao.stage).pk


def test_finalizada_exige_data_e_rascunho_nao_tem():
    with pytest.raises(IntegrityError):
        EvaluationFactory(status=EvaluationStatus.FINALIZED)


def test_pontos_nao_negativos():
    with pytest.raises(IntegrityError):
        EvaluationItemFactory(points=Decimal("-0.01"))


def test_pontos_ate_o_maximo_do_criterio():
    avaliacao = EvaluationFactory()
    criterio = StageCriterionFactory(stage=avaliacao.stage, max_score=Decimal("1.00"))
    item = EvaluationItem(
        evaluation=avaliacao, stage_criterion=criterio, points=Decimal("1.01")
    )
    with pytest.raises(ValidationError, match="Máximo do critério"):
        item.full_clean()


def test_criterio_de_outra_etapa_e_recusado():
    avaliacao = EvaluationFactory()
    item = EvaluationItem(
        evaluation=avaliacao,
        stage_criterion=StageCriterionFactory(),
        points=Decimal("0.5"),
    )
    with pytest.raises(ValidationError, match="outra etapa"):
        item.full_clean()


def test_avaliacao_de_etapa_de_outra_edicao_e_recusada():
    avaliacao = Evaluation(
        project=EvaluationFactory().project,
        stage=StageFactory(edition=EditionFactory()),
        teacher=EvaluationFactory().teacher,
    )
    with pytest.raises(ValidationError, match="edição do projeto"):
        avaliacao.full_clean()


# Nota consolidada da etapa


def test_uma_nota_por_projeto_e_etapa():
    nota = StageScoreFactory()
    with pytest.raises(IntegrityError):
        StageScoreFactory(project=nota.project, stage=nota.stage)


@pytest.mark.parametrize(
    ("status", "value"),
    [
        (ScoreStatus.PENDING, Decimal("1.00")),
        (ScoreStatus.DEFINITIVE, None),
        (ScoreStatus.ZERO_NO_SUBMISSION, Decimal("1.00")),
    ],
)
def test_valor_coerente_com_o_status(status, value):
    with pytest.raises(IntegrityError):
        StageScoreFactory(status=status, value=value)


def test_nota_definitiva_e_zero_sem_entrega_validos():
    assert StageScoreFactory(definitive=True).value == Decimal("2.50")
    zero = StageScoreFactory(status=ScoreStatus.ZERO_NO_SUBMISSION, value=0)
    assert zero.value == 0


# Etapa final (avaliador externo)


def test_um_formulario_por_edicao():
    formulario = FinalFormFactory()
    with pytest.raises(IntegrityError):
        FinalFormFactory(edition=formulario.edition)


def test_ordem_da_pergunta_unica_no_formulario():
    pergunta = FinalQuestionFactory()
    with pytest.raises(IntegrityError):
        FinalQuestionFactory(form=pergunta.form, order=pergunta.order)


@pytest.mark.parametrize(
    ("kind", "max_score"),
    [
        (QuestionKind.SCORE, None),
        (QuestionKind.SCORE, Decimal("0")),
        (QuestionKind.TEXT, Decimal("10")),
    ],
)
def test_pontuacao_maxima_coerente_com_o_tipo(kind, max_score):
    with pytest.raises(IntegrityError):
        FinalQuestionFactory(kind=kind, max_score=max_score)


def test_avaliador_avalia_o_projeto_uma_vez():
    avaliacao = FinalEvaluationFactory()
    with pytest.raises(IntegrityError):
        FinalEvaluationFactory(
            project=avaliacao.project,
            reviewer=avaliacao.reviewer,
            form=avaliacao.form,
        )


def test_avaliada_exige_data():
    with pytest.raises(IntegrityError):
        FinalEvaluationFactory(status=FinalEvaluationStatus.EVALUATED)


def test_avaliador_fora_da_edicao_e_recusado():
    avaliacao = FinalEvaluationFactory()
    outra = FinalEvaluation(
        project=avaliacao.project,
        reviewer=ExternalReviewerFactory(),
        form=avaliacao.form,
    )
    with pytest.raises(ValidationError, match="não está nesta edição"):
        outra.full_clean()


def test_uma_resposta_por_pergunta():
    resposta = FinalAnswerFactory()
    with pytest.raises(IntegrityError):
        FinalAnswerFactory(evaluation=resposta.evaluation, question=resposta.question)


def test_resposta_de_nota_acima_do_maximo_e_recusada():
    resposta = FinalAnswerFactory.build(evaluation=FinalEvaluationFactory())
    resposta.question = FinalQuestionFactory(form=resposta.evaluation.form)
    resposta.value = Decimal("10.01")
    with pytest.raises(ValidationError, match="Entre 0 e"):
        resposta.full_clean()


def test_resposta_de_texto_exige_texto():
    avaliacao = FinalEvaluationFactory()
    pergunta = FinalQuestionFactory(form=avaliacao.form, text=True)
    resposta = FinalAnswer(evaluation=avaliacao, question=pergunta, value=Decimal("5"))
    with pytest.raises(ValidationError, match="só o texto"):
        resposta.full_clean()


def test_pergunta_de_outro_formulario_e_recusada():
    resposta = FinalAnswer(
        evaluation=FinalEvaluationFactory(),
        question=FinalQuestionFactory(),
        value=Decimal("5"),
    )
    with pytest.raises(ValidationError, match="outro formulário"):
        resposta.full_clean()


# Factories válidas para os próximos apps


@pytest.mark.parametrize(
    "factory",
    [
        EvaluationFactory,
        EvaluationItemFactory,
        StageScoreFactory,
        FinalFormFactory,
        FinalQuestionFactory,
        FinalEvaluationFactory,
        FinalAnswerFactory,
    ],
)
def test_factory_gera_registro_valido(factory):
    factory().full_clean()


def test_traits_validos():
    EvaluationFactory(finalized=True).full_clean()
    FinalEvaluationFactory(evaluated=True).full_clean()
