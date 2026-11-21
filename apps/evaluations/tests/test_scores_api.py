from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    StudentFactory,
    TeacherCourseFactory,
    TeacherFactory,
    UserFactory,
)
from apps.editions.factories import StageCriterionFactory, StageFactory
from apps.evaluations.use_cases.apply_zero_for_missing_submission import (
    apply_zero_for_missing_submission,
)
from apps.evaluations.use_cases.evaluate_submission import evaluate_submission
from apps.projects.factories import (
    ProjectFactory,
    SubmissionFactory,
    SubmissionVersionFactory,
)
from apps.teams.enums import MemberRole

pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def avaliar(ctx, professor, p1="1.00", p2="1.50"):
    return evaluate_submission(
        actor=professor.user,
        project=ctx.project,
        stage=ctx.stage,
        items=[
            {"stage_criterion": ctx.c1, "points": Decimal(p1), "comment": "Bom."},
            {"stage_criterion": ctx.c2, "points": Decimal(p2)},
        ],
        comment="Detalhar custos.",
        finalize=True,
    )


def novo_professor(ctx):
    professor = TeacherFactory()
    TeacherCourseFactory(teacher=professor, course=ctx.project.challenge.course)
    return professor


@pytest.fixture
def ctx():
    # Entrega encerrada há 6 dias; duas avaliações para a nota ficar definitiva.
    projeto = ProjectFactory()
    etapa = StageFactory(
        edition=projeto.edition,
        starts_at=timezone.now() - timedelta(days=20),
        min_evaluations=2,
    )
    SubmissionVersionFactory(
        submission=SubmissionFactory(project=projeto, stage=etapa),
        submitted_at=etapa.ends_at - timedelta(days=1),
    )
    return SimpleNamespace(
        project=projeto,
        stage=etapa,
        url=f"/api/projects/{projeto.pk}/scores",
        aluno=projeto.team.members.get(role=MemberRole.LEADER).student.user,
        c1=StageCriterionFactory(stage=etapa, max_score=Decimal("1.50")),
        c2=StageCriterionFactory(stage=etapa, max_score=Decimal("1.50")),
    )


def etapa_0(response):
    return response.data["stages"][0]


def test_com_uma_avaliacao_a_nota_fica_pendente_e_oculta(ctx):
    avaliar(ctx, novo_professor(ctx))

    response = client_for(ctx.aluno).get(ctx.url)

    assert response.status_code == 200
    etapa = etapa_0(response)
    assert etapa["status"] == "PENDING"
    assert etapa["value"] is None
    assert etapa["feedback"] == []
    assert etapa["criteria"][0]["average"] is None
    assert etapa["evaluation_count"] == 1
    assert etapa["min_evaluators"] == 2


def test_com_o_minimo_de_avaliacoes_mostra_media_e_feedback(ctx):
    avaliar(ctx, novo_professor(ctx), p1="1.00", p2="1.50")
    avaliar(ctx, novo_professor(ctx), p1="0.50", p2="1.50")

    etapa = etapa_0(client_for(ctx.aluno).get(ctx.url))

    assert etapa["status"] == "FINALIZED"
    assert etapa["value"] == "2.25"
    assert etapa["criteria"][0]["average"] == "0.75"
    assert len(etapa["feedback"]) == 2
    assert etapa["feedback"][0]["items"][0]["criterion_name"]
    # O feedback não identifica o professor (P-44).
    assert set(etapa["feedback"][0]) == {"comment", "items"}


def test_equipe_que_nao_entregou_mostra_zero(ctx):
    sem_entrega = StageFactory(
        edition=ctx.project.edition, starts_at=timezone.now() - timedelta(days=20)
    )
    apply_zero_for_missing_submission(project=ctx.project, stage=sem_entrega)

    response = client_for(ctx.aluno).get(ctx.url)

    etapa = next(
        e for e in response.data["stages"] if e["stage"]["id"] == sem_entrega.pk
    )
    assert etapa["status"] == "FINALIZED"
    assert etapa["value"] == "0.00"
    assert etapa["deliverable_status"] == "NOT_DELIVERED"


def test_professor_do_curso_e_admin_podem_consultar(ctx):
    professor = novo_professor(ctx)
    admin = UserFactory(role=UserRole.ADMIN)

    assert client_for(professor.user).get(ctx.url).status_code == 200
    assert client_for(admin).get(ctx.url).status_code == 200


def test_aluno_de_outra_equipe_e_recusado(ctx):
    outro = StudentFactory().user

    assert client_for(outro).get(ctx.url).status_code == 403


def test_professor_de_outro_curso_e_recusado(ctx):
    outro = TeacherCourseFactory().teacher.user

    assert client_for(outro).get(ctx.url).status_code == 403


def test_exige_login(ctx):
    assert APIClient().get(ctx.url).status_code == 401


def test_projeto_inexistente_da_404(ctx):
    response = client_for(ctx.aluno).get("/api/projects/999999/scores")

    assert response.status_code == 404
