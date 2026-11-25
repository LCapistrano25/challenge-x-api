from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.factories import CourseFactory
from apps.editions.enums import EditionStatus
from apps.evaluations.factories import FinalEvaluationFactory
from apps.evaluations.models import StageScore
from apps.results.models import ProjectResult

pytestmark = pytest.mark.django_db

ROUTES = ["results/calculate", "finalists", "results/homologate"]


def url(edition, suffix):
    return f"/api/admin/editions/{edition.pk}/{suffix}"


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def post(client, edition, route, project_ids=(1,)):
    body = {"project_ids": list(project_ids)} if route == "finalists" else {}
    return client.post(url(edition, route), body, format="json")


def error_code(response):
    return response.data["error"]["code"]


def test_fluxo_completo_200(admin, edition, make_project):
    project = make_project("2.50", "3.00")
    client = client_for(admin)

    calculated = post(client, edition, "results/calculate")
    chosen = post(client, edition, "finalists", [project.pk])
    approved = post(client, edition, "results/homologate")

    assert [r.status_code for r in (calculated, chosen, approved)] == [200] * 3
    assert calculated.json()["approved_at"] is None
    assert calculated.json()["results"][0]["finalist"] is False
    body = approved.json()
    assert body["edition_id"] == edition.pk
    assert body["approved_at"] is not None
    assert body["excluded"] == []
    [row] = body["results"]
    assert row["project"] == {"id": project.pk, "title": project.title}
    assert row["team"]["id"] == project.team_id
    assert row["course"]["id"] == project.challenge.course_id
    assert row["category"] is None
    assert row["final_score"] == "5.50"
    assert row["course_rank"] == 1
    assert row["finalist"] is True


def test_excluidos_aparecem_com_o_motivo(admin, edition, make_project):
    project = make_project("2.50")

    response = post(client_for(admin), edition, "results/calculate")

    assert response.json()["results"] == []
    assert response.json()["excluded"] == [
        {
            "project_id": project.pk,
            "team_id": project.team_id,
            "reason": "PENDING_SCORE",
        }
    ]


def test_resultados_ordenados_por_curso_e_posicao(admin, edition, make_project):
    zoo = CourseFactory(name="Zz Curso de Teste")
    adm = CourseFactory(name="Aa Curso de Teste")
    last = make_project("3.00", "3.00", course=zoo)
    second = make_project("1.00", "1.00", course=adm)
    first = make_project("2.00", "2.00", course=adm)

    response = post(client_for(admin), edition, "results/calculate")

    assert [r["project"]["id"] for r in response.json()["results"]] == [
        first.pk,
        second.pk,
        last.pk,
    ]


@pytest.mark.parametrize("route", ROUTES)
def test_401_sem_login(edition, route):
    assert post(APIClient(), edition, route).status_code == 401


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    "role", [UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_403_para_quem_nao_e_admin(edition, route, role):
    client = client_for(UserFactory(role=role))

    assert post(client, edition, route).status_code == 403


@pytest.mark.parametrize("route", ROUTES)
def test_404_edicao_inexistente(admin, route):
    class Missing:
        pk = 999999

    response = post(client_for(admin), Missing, route)

    assert response.status_code == 404
    assert error_code(response) == "not_found"


@pytest.mark.parametrize(
    "body",
    [{"project_ids": []}, {"project_ids": ["x"]}, "repetida", "fora"],
)
def test_400_nos_finalistas(admin, edition, make_project, body):
    project = make_project("3.00", "3.00")
    client = client_for(admin)
    post(client, edition, "results/calculate")
    if body == "repetida":
        body = {"project_ids": [project.pk, project.pk]}
    elif body == "fora":
        body = {"project_ids": [999999]}

    response = client.post(url(edition, "finalists"), body, format="json")

    assert response.status_code == 400
    assert error_code(response) == "validation_error"
    assert "project_ids" in response.data["error"]["details"]


@pytest.mark.parametrize(
    "case, route, code",
    [
        ("sem_etapa", "results/calculate", "no_scored_stages"),
        ("encerrada", "results/calculate", "edition_closed"),
        ("encerrada", "finalists", "edition_closed"),
        ("encerrada", "results/homologate", "edition_closed"),
        ("homologada", "results/calculate", "results_already_approved"),
        ("homologada", "finalists", "results_already_approved"),
        ("homologada", "results/homologate", "results_already_approved"),
        ("sem_calculo", "finalists", "results_not_calculated"),
        ("sem_calculo", "results/homologate", "results_not_calculated"),
        ("sem_finalista", "results/homologate", "no_finalists"),
        ("defasada", "results/homologate", "results_outdated"),
        ("avaliado", "finalists", "finalist_already_evaluated"),
    ],
)
def test_409(admin, edition, request, case, route, code):
    client = client_for(admin)
    ids = [1]
    if case != "sem_etapa":
        make_project = request.getfixturevalue("make_project")
        first = make_project("3.00", "3.00")
        second = make_project("1.00", "1.00")
        ids = [second.pk]
        if case != "sem_calculo":
            post(client, edition, "results/calculate")
        if case == "homologada":
            ProjectResult.objects.update(approved_at=timezone.now())
        elif case == "defasada":
            post(client, edition, "finalists", [first.pk])
            StageScore.objects.filter(project=first).update(value=Decimal("2.00"))
        elif case == "avaliado":
            post(client, edition, "finalists", [first.pk])
            FinalEvaluationFactory(project=first)
    if case == "encerrada":
        edition.status = EditionStatus.CLOSED
        edition.save()

    response = post(client, edition, route, ids)

    assert response.status_code == 409
    assert error_code(response) == code


@pytest.mark.parametrize("route", ROUTES)
def test_405_get(admin, edition, route):
    assert client_for(admin).get(url(edition, route)).status_code == 405


def test_finalistas_sem_lista_escolhem_os_3_primeiros_do_curso(
    admin, edition, make_project
):
    projects = [make_project(v, v) for v in ("3.00", "2.50", "2.00", "1.00")]
    client = client_for(admin)
    post(client, edition, "results/calculate")

    response = client.post(url(edition, "finalists"), {}, format="json")

    assert response.status_code == 200
    chosen = {
        row["project"]["id"] for row in response.json()["results"] if row["finalist"]
    }
    assert chosen == {p.pk for p in projects[:3]}
