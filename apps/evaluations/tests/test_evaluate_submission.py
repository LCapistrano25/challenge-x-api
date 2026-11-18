from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotTeacherActor
from apps.accounts.factories import TeacherCourseFactory, TeacherFactory, UserFactory
from apps.editions.factories import StageCriterionFactory, StageFactory
from apps.evaluations.enums import EvaluationStatus, ScoreStatus
from apps.evaluations.models import Evaluation, StageScore
from apps.evaluations.use_cases.evaluate_submission import evaluate_submission
from apps.projects.factories import SubmissionFactory, SubmissionVersionFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx():
    versao = SubmissionVersionFactory()
    projeto, etapa = versao.submission.project, versao.submission.stage
    professor = TeacherFactory()
    TeacherCourseFactory(teacher=professor, course=projeto.challenge.course)
    return SimpleNamespace(
        actor=professor.user,
        project=projeto,
        stage=etapa,
        c1=StageCriterionFactory(stage=etapa, max_score=Decimal("1.50")),
        c2=StageCriterionFactory(stage=etapa, max_score=Decimal("1.50")),
    )


def itens(ctx, p1="1.00", p2="1.50"):
    return [
        {"stage_criterion": ctx.c1, "points": Decimal(p1), "comment": "Bom."},
        {"stage_criterion": ctx.c2, "points": Decimal(p2)},
    ]


def avaliar(ctx, **kwargs):
    kwargs.setdefault("actor", ctx.actor)
    kwargs.setdefault("items", itens(ctx))
    return evaluate_submission(project=ctx.project, stage=ctx.stage, **kwargs)


def test_salva_rascunho_com_os_itens(ctx):
    avaliacao = avaliar(ctx, comment="Detalhar custos.")

    assert avaliacao.status == EvaluationStatus.DRAFT
    assert avaliacao.finalized_at is None
    assert avaliacao.comment == "Detalhar custos."
    assert avaliacao.items.count() == 2
    assert not StageScore.objects.exists()


def test_salvar_de_novo_atualiza_a_mesma_avaliacao(ctx):
    primeira = avaliar(ctx)

    segunda = avaliar(ctx, items=itens(ctx, p1="0.50")[:1])

    assert segunda.pk == primeira.pk
    assert Evaluation.objects.count() == 1
    assert segunda.items.get().points == Decimal("0.50")


def test_finalizar_fecha_a_avaliacao_e_calcula_a_nota(ctx):
    avaliacao = avaliar(ctx, finalize=True)

    assert avaliacao.status == EvaluationStatus.FINALIZED
    assert avaliacao.finalized_at is not None
    nota = StageScore.objects.get(project=ctx.project, stage=ctx.stage)
    assert nota.status == ScoreStatus.DEFINITIVE
    assert nota.value == Decimal("2.50")


def test_so_professor_avalia(ctx):
    with pytest.raises(NotTeacherActor):
        avaliar(ctx, actor=UserFactory(role=UserRole.ADMIN))


def test_usuario_professor_sem_perfil_nao_avalia(ctx):
    with pytest.raises(NotTeacherActor):
        avaliar(ctx, actor=UserFactory(role=UserRole.TEACHER))


def test_professor_de_outro_curso_nao_avalia(ctx):
    outro = TeacherCourseFactory().teacher

    with pytest.raises(ValidationError, match="vínculo ativo"):
        avaliar(ctx, actor=outro.user)


def test_etapa_de_outra_edicao_e_recusada(ctx):
    with pytest.raises(ValidationError, match="projeto"):
        evaluate_submission(
            actor=ctx.actor, project=ctx.project, stage=StageFactory(), items=[]
        )


def test_etapa_sem_avaliacao_do_professor_e_recusada(ctx):
    formacao = StageFactory(edition=ctx.project.edition, formation=True)

    with pytest.raises(ValidationError, match="não tem avaliação"):
        evaluate_submission(
            actor=ctx.actor, project=ctx.project, stage=formacao, items=[]
        )


def test_projeto_sem_entrega_valida_e_recusado(ctx):
    sem_entrega = SubmissionFactory(project=ctx.project).stage

    with pytest.raises(ValidationError, match="entrega válida"):
        evaluate_submission(
            actor=ctx.actor, project=ctx.project, stage=sem_entrega, items=[]
        )


def test_pontos_acima_do_maximo_do_criterio_sao_recusados(ctx):
    with pytest.raises(ValidationError, match="Máximo do critério"):
        avaliar(ctx, items=itens(ctx, p1="1.51"))


def test_pontos_negativos_sao_recusados(ctx):
    with pytest.raises(ValidationError):
        avaliar(ctx, items=itens(ctx, p1="-0.10"))


def test_criterio_de_outra_etapa_e_recusado(ctx):
    alheio = StageCriterionFactory(stage=StageFactory(edition=ctx.project.edition))

    with pytest.raises(ValidationError, match="outra etapa"):
        avaliar(ctx, items=[{"stage_criterion": alheio, "points": Decimal("0.50")}])


def test_finalizar_sem_todos_os_criterios_e_recusado(ctx):
    with pytest.raises(ValidationError, match="todos os critérios"):
        avaliar(ctx, items=itens(ctx)[:1], finalize=True)


def test_avaliacao_finalizada_nao_pode_ser_alterada(ctx):
    avaliar(ctx, finalize=True)

    with pytest.raises(ValidationError, match="já foi finalizada"):
        avaliar(ctx, items=itens(ctx, p1="0.00"))


def test_nao_finaliza_depois_do_prazo_de_avaliacao():
    etapa = StageFactory(starts_at=timezone.now() - timedelta(days=30))
    assert etapa.evaluation_ends_at < timezone.now()
    versao = SubmissionVersionFactory(
        submission__stage=etapa,
        submission__project__edition=etapa.edition,
        submitted_at=etapa.ends_at - timedelta(days=1),
    )
    professor = TeacherFactory()
    projeto = versao.submission.project
    TeacherCourseFactory(teacher=professor, course=projeto.challenge.course)
    criterio = StageCriterionFactory(stage=etapa, max_score=Decimal("1.50"))

    with pytest.raises(ValidationError, match="prazo de avaliação"):
        evaluate_submission(
            actor=professor.user,
            project=projeto,
            stage=etapa,
            items=[{"stage_criterion": criterio, "points": Decimal("1.00")}],
            finalize=True,
        )
    assert not Evaluation.objects.filter(status=EvaluationStatus.FINALIZED).exists()


def test_criterio_repetido_e_recusado(ctx):
    repetido = [*itens(ctx), {"stage_criterion": ctx.c1, "points": Decimal("0.50")}]

    with pytest.raises(ValidationError, match="repetido"):
        avaliar(ctx, items=repetido)
