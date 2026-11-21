from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.factories import TeacherCourseFactory
from apps.editions.factories import StageCriterionFactory, StageFactory
from apps.evaluations.exceptions import TeacherNotInCourse
from apps.evaluations.factories import EvaluationFactory, EvaluationItemFactory
from apps.evaluations.rules import (
    ensure_all_criteria_scored,
    ensure_evaluation_is_draft,
    ensure_has_valid_submission,
    ensure_stage_is_evaluable,
    ensure_submission_period_closed,
    ensure_teacher_in_challenge_course,
)
from apps.projects.factories import SubmissionFactory, SubmissionVersionFactory

pytestmark = pytest.mark.django_db


def test_professor_do_curso_do_desafio_pode_avaliar():
    avaliacao = EvaluationFactory()
    TeacherCourseFactory(
        teacher=avaliacao.teacher, course=avaliacao.project.challenge.course
    )

    ensure_teacher_in_challenge_course(avaliacao.teacher, avaliacao.project)


def test_professor_de_outro_curso_nao_pode_avaliar():
    avaliacao = EvaluationFactory()
    TeacherCourseFactory(teacher=avaliacao.teacher)

    with pytest.raises(TeacherNotInCourse):
        ensure_teacher_in_challenge_course(avaliacao.teacher, avaliacao.project)


def test_vinculo_inativo_nao_conta():
    avaliacao = EvaluationFactory()
    TeacherCourseFactory(
        teacher=avaliacao.teacher,
        course=avaliacao.project.challenge.course,
        active=False,
    )

    with pytest.raises(TeacherNotInCourse):
        ensure_teacher_in_challenge_course(avaliacao.teacher, avaliacao.project)


def test_etapa_de_entrega_pontuada_e_avaliavel():
    ensure_stage_is_evaluable(StageFactory())


def test_etapa_de_formacao_nao_e_avaliavel():
    with pytest.raises(ValidationError, match="não tem avaliação"):
        ensure_stage_is_evaluable(StageFactory(formation=True))


def test_entrega_com_versao_no_prazo_e_valida():
    versao = SubmissionVersionFactory()
    submissao = versao.submission

    ensure_has_valid_submission(submissao.project, submissao.stage)


def test_projeto_sem_entrega_nao_tem_o_que_avaliar():
    avaliacao = EvaluationFactory()

    with pytest.raises(ValidationError, match="entrega válida"):
        ensure_has_valid_submission(avaliacao.project, avaliacao.stage)


def test_entrega_so_com_versao_fora_do_prazo_nao_e_valida():
    submissao = SubmissionFactory()
    SubmissionVersionFactory(
        submission=submissao,
        submitted_at=submissao.stage.ends_at + timedelta(seconds=1),
    )

    with pytest.raises(ValidationError, match="entrega válida"):
        ensure_has_valid_submission(submissao.project, submissao.stage)


def test_avaliacao_finalizada_nao_muda():
    with pytest.raises(ValidationError, match="já foi finalizada"):
        ensure_evaluation_is_draft(EvaluationFactory(finalized=True))


def test_rascunho_pode_mudar():
    ensure_evaluation_is_draft(EvaluationFactory())


def test_finalizar_exige_todos_os_criterios():
    avaliacao = EvaluationFactory()
    pontuado = StageCriterionFactory(stage=avaliacao.stage)
    StageCriterionFactory(stage=avaliacao.stage)
    EvaluationItemFactory(evaluation=avaliacao, stage_criterion=pontuado)

    with pytest.raises(ValidationError, match="todos os critérios"):
        ensure_all_criteria_scored(avaliacao)


def test_todos_os_criterios_pontuados_pode_finalizar():
    avaliacao = EvaluationFactory()
    criterio = StageCriterionFactory(stage=avaliacao.stage)
    EvaluationItemFactory(evaluation=avaliacao, stage_criterion=criterio)

    ensure_all_criteria_scored(avaliacao)


def test_etapa_sem_criterios_nao_finaliza():
    with pytest.raises(ValidationError, match="todos os critérios"):
        ensure_all_criteria_scored(EvaluationFactory())


def test_prazo_de_entrega_encerrado_libera_a_finalizacao():
    etapa = StageFactory(starts_at=timezone.now() - timedelta(days=20))

    ensure_submission_period_closed(SubmissionFactory(stage=etapa).project, etapa)


def test_prazo_de_entrega_aberto_barra_a_finalizacao():
    submissao = SubmissionFactory()

    with pytest.raises(ValidationError, match="prazo de entrega"):
        ensure_submission_period_closed(submissao.project, submissao.stage)
