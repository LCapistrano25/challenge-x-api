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
from apps.editions.enums import EditionStatus
from apps.editions.factories import StageCriterionFactory, StageFactory
from apps.evaluations.enums import EvaluationStatus
from apps.evaluations.models import Evaluation
from apps.projects.factories import (
    ProjectFactory,
    SubmissionFactory,
    SubmissionVersionFactory,
)

pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def error_code(response):
    return response.data["error"]["code"]


@pytest.fixture
def ctx():
    # Entrega encerrada há 6 dias e avaliação aberta até amanhã.
    projeto = ProjectFactory(team__edition__status=EditionStatus.PUBLISHED)
    etapa = StageFactory(
        edition=projeto.edition, starts_at=timezone.now() - timedelta(days=20)
    )
    SubmissionVersionFactory(
        submission=SubmissionFactory(project=projeto, stage=etapa),
        submitted_at=etapa.ends_at - timedelta(days=1),
    )
    professor = TeacherFactory()
    TeacherCourseFactory(teacher=professor, course=projeto.challenge.course)
    return SimpleNamespace(
        user=professor.user,
        url=f"/api/projects/{projeto.pk}/stages/{etapa.pk}/evaluation",
        c1=StageCriterionFactory(stage=etapa, max_score=Decimal("1.50")),
        c2=StageCriterionFactory(stage=etapa, max_score=Decimal("1.50")),
    )


def corpo(ctx, status="DRAFT", p1="1.25", p2="1.50"):
    return {
        "status": status,
        "comment": "Detalhar custos.",
        "items": [
            {"stage_criterion_id": ctx.c1.pk, "points": p1, "comment": "Bom."},
            {"stage_criterion_id": ctx.c2.pk, "points": p2},
        ],
    }


# GET /api/projects/{project_id}/stages/{stage_id}/evaluation (RF38)


def test_get_devolve_os_criterios_e_nenhuma_avaliacao_ainda(ctx):
    response = client_for(ctx.user).get(ctx.url)

    assert response.status_code == 200
    assert response.data["evaluation"] is None
    assert [c["stage_criterion_id"] for c in response.data["criteria"]] == [
        ctx.c1.pk,
        ctx.c2.pk,
    ]


def test_get_devolve_a_avaliacao_do_professor_com_o_total(ctx):
    client = client_for(ctx.user)
    client.put(ctx.url, corpo(ctx), format="json")

    response = client.get(ctx.url)

    assert response.data["evaluation"]["status"] == "DRAFT"
    assert response.data["evaluation"]["total"] == "2.75"


def test_get_exige_login(ctx):
    assert APIClient().get(ctx.url).status_code == 403


def test_get_so_para_professor(ctx):
    aluno = StudentFactory().user

    assert client_for(aluno).get(ctx.url).status_code == 403


def test_get_de_professor_de_outro_curso_e_403(ctx):
    outro = TeacherCourseFactory().teacher.user

    response = client_for(outro).get(ctx.url)

    assert response.status_code == 403
    assert error_code(response) == "teacher_not_in_course"


def test_get_de_projeto_inexistente_e_404(ctx):
    response = client_for(ctx.user).get("/api/projects/999999/stages/1/evaluation")

    assert response.status_code == 404


# PUT /api/projects/{project_id}/stages/{stage_id}/evaluation (RF38)


def test_put_salva_o_rascunho(ctx):
    response = client_for(ctx.user).put(ctx.url, corpo(ctx), format="json")

    assert response.status_code == 200
    assert response.data["status"] == "DRAFT"
    assert response.data["finalized_at"] is None
    assert len(response.data["items"]) == 2


def test_put_finaliza_a_avaliacao(ctx):
    response = client_for(ctx.user).put(
        ctx.url, corpo(ctx, status="FINALIZED"), format="json"
    )

    assert response.status_code == 200
    assert response.data["status"] == "FINALIZED"
    assert response.data["finalized_at"] is not None


def test_put_exige_login(ctx):
    response = APIClient().put(ctx.url, corpo(ctx), format="json")

    assert response.status_code == 403


def test_put_so_para_professor(ctx):
    admin = UserFactory(role=UserRole.ADMIN)

    assert client_for(admin).put(ctx.url, corpo(ctx), format="json").status_code == 403


def test_put_de_professor_de_outro_curso_e_403(ctx):
    outro = TeacherCourseFactory().teacher.user

    response = client_for(outro).put(ctx.url, corpo(ctx), format="json")

    assert response.status_code == 403
    assert not Evaluation.objects.exists()


def test_put_com_pontos_acima_do_maximo_e_400(ctx):
    response = client_for(ctx.user).put(ctx.url, corpo(ctx, p1="1.51"), format="json")

    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_put_sem_status_e_400(ctx):
    body = corpo(ctx)
    del body["status"]

    assert client_for(ctx.user).put(ctx.url, body, format="json").status_code == 400


def test_put_de_avaliacao_finalizada_e_400(ctx):
    client = client_for(ctx.user)
    client.put(ctx.url, corpo(ctx, status="FINALIZED"), format="json")

    response = client.put(ctx.url, corpo(ctx, p1="0.00"), format="json")

    assert response.status_code == 400
    assert Evaluation.objects.get().status == EvaluationStatus.FINALIZED


def test_put_de_projeto_inexistente_e_404(ctx):
    response = client_for(ctx.user).put(
        "/api/projects/999999/stages/1/evaluation", corpo(ctx), format="json"
    )

    assert response.status_code == 404


# GET /api/teacher/projects (RF37)

PAINEL = "/api/teacher/projects"


def test_painel_lista_o_projeto_do_curso_do_professor(ctx):
    response = client_for(ctx.user).get(PAINEL)

    assert response.status_code == 200
    assert response.data["count"] == 1
    linha = response.data["results"][0]
    assert linha["deliverable_status"] == "SUBMITTED"
    assert linha["my_evaluation_status"] == "NOT_STARTED"
    assert linha["evaluation_count"] == 0
    assert linha["min_evaluators"] == 1


def test_painel_acompanha_a_avaliacao_do_professor(ctx):
    client = client_for(ctx.user)
    client.put(ctx.url, corpo(ctx), format="json")
    assert client.get(PAINEL).data["results"][0]["my_evaluation_status"] == "DRAFT"

    client.put(ctx.url, corpo(ctx, status="FINALIZED"), format="json")
    linha = client.get(PAINEL).data["results"][0]
    assert linha["my_evaluation_status"] == "FINALIZED"
    assert linha["evaluation_count"] == 1


def test_painel_nao_mostra_projeto_de_outro_curso(ctx):
    outro = TeacherCourseFactory().teacher.user

    assert client_for(outro).get(PAINEL).data["count"] == 0


def test_painel_filtra_por_curso(ctx):
    client = client_for(ctx.user)
    curso = TeacherCourseFactory(teacher=ctx.user.teacher).course

    assert client.get(PAINEL, {"course_id": curso.pk}).data["count"] == 0


def test_painel_pending_only_some_depois_de_finalizar(ctx):
    client = client_for(ctx.user)
    assert client.get(PAINEL, {"pending_only": "true"}).data["count"] == 1

    client.put(ctx.url, corpo(ctx, status="FINALIZED"), format="json")

    assert client.get(PAINEL, {"pending_only": "true"}).data["count"] == 0


def test_painel_marca_entrega_nao_enviada_e_nao_entregue():
    projeto = ProjectFactory(team__edition__status=EditionStatus.PUBLISHED)
    professor = TeacherFactory()
    TeacherCourseFactory(teacher=professor, course=projeto.challenge.course)
    aberta = StageFactory(edition=projeto.edition)
    vencida = StageFactory(
        edition=projeto.edition, starts_at=timezone.now() - timedelta(days=20)
    )

    linhas = client_for(professor.user).get(PAINEL).data["results"]

    status = {linha["stage"]["id"]: linha["deliverable_status"] for linha in linhas}
    assert status == {aberta.pk: "NOT_SUBMITTED", vencida.pk: "NOT_DELIVERED"}


def test_painel_exige_login():
    assert APIClient().get(PAINEL).status_code == 403


def test_painel_so_para_professor():
    assert client_for(StudentFactory().user).get(PAINEL).status_code == 403
