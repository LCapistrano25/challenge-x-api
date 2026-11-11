from datetime import timedelta

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
from apps.editions.factories import CategoryFactory, ChallengeFactory, StageFactory
from apps.projects.factories import ProjectFactory
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db


def url(team, suffix=""):
    return f"/api/teams/{team.pk}/project{suffix}"


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def error_code(response):
    return response.data["error"]["code"]


@pytest.fixture
def team():
    team = TeamFactory()
    now = timezone.now()
    StageFactory(
        formation=True,
        edition=team.edition,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )
    return team


@pytest.fixture
def leader(team):
    return team.members.get(role=MemberRole.LEADER).student.user


@pytest.fixture
def challenge(team):
    course = team.members.get(role=MemberRole.LEADER).student.course
    return ChallengeFactory(edition=team.edition, course=course)


@pytest.fixture
def member(team):
    return TeamMemberFactory(team=team).student.user


# GET /api/teams/{team_id}/project/options (RF29, RF50)


def test_opcoes_devolvem_desafios_elegiveis_e_categorias(team, member, challenge):
    ChallengeFactory(edition=team.edition)  # curso sem integrante
    category = CategoryFactory(edition=team.edition, description="Categoria A")
    CategoryFactory(edition=team.edition, active=False)

    response = client_for(member).get(url(team, "/options"))

    assert response.status_code == 200
    assert response.data["challenges"] == [
        {
            "id": challenge.pk,
            "description": challenge.description,
            "course": {"id": challenge.course.pk, "name": challenge.course.name},
            "sdg": {
                "id": challenge.sdg.pk,
                "number": challenge.sdg.number,
                "title": challenge.sdg.title,
            },
        }
    ]
    assert response.data["categories"] == [
        {"id": category.pk, "name": category.name, "description": "Categoria A"}
    ]


def test_opcoes_exigem_login(team):
    assert APIClient().get(url(team, "/options")).status_code == 403


def test_opcoes_recusam_quem_nao_e_aluno(team):
    admin = UserFactory(role=UserRole.ADMIN)
    assert client_for(admin).get(url(team, "/options")).status_code == 403


def test_opcoes_recusam_aluno_de_fora_da_equipe(team):
    de_fora = StudentFactory().user
    response = client_for(de_fora).get(url(team, "/options"))
    assert response.status_code == 403
    assert error_code(response) == "project_access_denied"


def test_opcoes_de_equipe_inexistente(member):
    response = client_for(member).get("/api/teams/999999/project/options")
    assert response.status_code == 404


# GET /api/teams/{team_id}/project (RF30, RF20)


def full_project(team, challenge):
    return ProjectFactory(
        team=team,
        challenge=challenge,
        title="Água limpa",
        category=CategoryFactory(edition=team.edition),
    )


def test_aluno_integrante_consulta_o_projeto(team, member, challenge):
    project = full_project(team, challenge)

    response = client_for(member).get(url(team))

    assert response.status_code == 200
    data = response.data
    assert (data["id"], data["team_id"], data["edition_id"]) == (
        project.pk,
        team.pk,
        team.edition_id,
    )
    assert data["title"] == "Água limpa"
    assert data["summary"] == "Resumo da proposta."
    assert data["objective"] == ""
    assert data["status"] == "IN_PROGRESS"
    assert data["challenge"]["id"] == challenge.pk
    assert data["category"] == {
        "id": project.category.pk,
        "name": project.category.name,
    }
    assert {c["id"] for c in data["courses"]} == {
        m.student.course_id for m in team.members.all()
    }


def test_projeto_sem_desafio_mostra_desafio_nulo(team, member):
    ProjectFactory(team=team, challenge=None, title="")

    response = client_for(member).get(url(team))

    assert response.status_code == 200
    assert response.data["challenge"] is None
    assert response.data["category"] is None


def test_admin_consulta_qualquer_projeto(team, challenge):
    full_project(team, challenge)
    admin = UserFactory(role=UserRole.ADMIN)
    assert client_for(admin).get(url(team)).status_code == 200


def test_professor_do_curso_do_desafio_consulta(team, challenge):
    full_project(team, challenge)
    link = TeacherCourseFactory(course=challenge.course)
    assert client_for(link.teacher.user).get(url(team)).status_code == 200


def test_professor_de_outro_curso_e_recusado(team, challenge):
    full_project(team, challenge)
    teacher = TeacherFactory().user
    response = client_for(teacher).get(url(team))
    assert response.status_code == 403
    assert error_code(response) == "project_access_denied"


def test_professor_com_vinculo_inativo_e_recusado(team, challenge):
    full_project(team, challenge)
    link = TeacherCourseFactory(course=challenge.course, active=False)
    assert client_for(link.teacher.user).get(url(team)).status_code == 403


def test_professor_nao_ve_projeto_sem_desafio(team):
    ProjectFactory(team=team, challenge=None)
    link = TeacherCourseFactory()
    assert client_for(link.teacher.user).get(url(team)).status_code == 403


def test_aluno_de_fora_da_equipe_nao_consulta(team, challenge):
    full_project(team, challenge)
    assert client_for(StudentFactory().user).get(url(team)).status_code == 403


def test_consulta_do_projeto_exige_login(team):
    assert APIClient().get(url(team)).status_code == 403


def test_consulta_de_equipe_sem_projeto_da_404(team, member):
    response = client_for(member).get(url(team))
    assert response.status_code == 404


def test_consulta_de_equipe_inexistente(member):
    assert client_for(member).get("/api/teams/999999/project").status_code == 404


# PUT /api/teams/{team_id}/project/challenge (RF29)


def test_lider_escolhe_o_desafio(team, leader, challenge):
    response = client_for(leader).put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )

    assert response.status_code == 200
    assert response.data["challenge"]["id"] == challenge.pk
    assert response.data["team_id"] == team.pk
    assert response.data["title"] == ""


def test_escolher_com_desafio_inexistente_e_erro_de_validacao(team, leader):
    response = client_for(leader).put(
        url(team, "/challenge"), {"challenge_id": 999999}, format="json"
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"
    assert "challenge_id" in response.data["error"]["details"]


def test_escolher_sem_o_campo_e_erro_de_validacao(team, leader):
    response = client_for(leader).put(url(team, "/challenge"), {}, format="json")
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_escolher_desafio_nao_elegivel(team, leader):
    estranho = ChallengeFactory(edition=team.edition)
    response = client_for(leader).put(
        url(team, "/challenge"), {"challenge_id": estranho.pk}, format="json"
    )
    assert response.status_code == 400
    assert error_code(response) == "challenge_not_eligible"


def test_escolher_recusa_quem_nao_e_lider(team, member, challenge):
    response = client_for(member).put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )
    assert response.status_code == 403
    assert error_code(response) == "not_team_leader"


def test_escolher_recusa_quem_nao_e_aluno(team, challenge):
    admin = UserFactory(role=UserRole.ADMIN)
    response = client_for(admin).put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )
    assert response.status_code == 403


def test_escolher_exige_login(team, challenge):
    response = APIClient().put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )
    assert response.status_code == 403


def test_escolher_fora_do_prazo(team, leader, challenge):
    team.edition.stages.all().delete()
    response = client_for(leader).put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )
    assert response.status_code == 409
    assert error_code(response) == "formation_closed"


def test_escolher_em_equipe_inexistente(leader, challenge):
    response = client_for(leader).put(
        "/api/teams/999999/project/challenge",
        {"challenge_id": challenge.pk},
        format="json",
    )
    assert response.status_code == 404


# PUT /api/teams/{team_id}/project/details (RF30)

DETAILS = {"title": "Água limpa", "summary": "Sensores no campus."}


@pytest.fixture
def project(team, challenge):
    return ProjectFactory(team=team, challenge=challenge, title="", summary="")


def test_lider_cadastra_os_dados(team, leader, project):
    response = client_for(leader).put(
        url(team, "/details"), {**DETAILS, "objective": "Reduzir 20%."}, format="json"
    )

    assert response.status_code == 200
    assert response.data["id"] == project.pk
    assert response.data["title"] == "Água limpa"
    assert response.data["summary"] == "Sensores no campus."
    assert response.data["objective"] == "Reduzir 20%."


def test_lider_atualiza_os_dados(team, leader, project):
    client = client_for(leader)
    client.put(url(team, "/details"), DETAILS, format="json")

    response = client.put(
        url(team, "/details"), {"title": "Novo", "summary": "Outro"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["title"] == "Novo"
    assert response.data["objective"] == ""


@pytest.mark.parametrize(
    "body",
    [
        {"summary": "x"},
        {"title": "x"},
        {"title": "", "summary": "x"},
        {"title": "x", "summary": "   "},
        {"title": "x" * 201, "summary": "x"},
    ],
)
def test_dados_invalidos_sao_erro_de_validacao(team, leader, project, body):
    response = client_for(leader).put(url(team, "/details"), body, format="json")
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_dados_recusam_quem_nao_e_lider(team, member, project):
    response = client_for(member).put(url(team, "/details"), DETAILS, format="json")
    assert response.status_code == 403
    assert error_code(response) == "not_team_leader"


def test_dados_recusam_quem_nao_e_aluno(team, project):
    teacher = TeacherFactory().user
    response = client_for(teacher).put(url(team, "/details"), DETAILS, format="json")
    assert response.status_code == 403


def test_dados_exigem_login(team, project):
    assert (
        APIClient().put(url(team, "/details"), DETAILS, format="json").status_code
        == 403
    )


def test_dados_fora_do_prazo(team, leader, project):
    team.edition.stages.all().delete()
    response = client_for(leader).put(url(team, "/details"), DETAILS, format="json")
    assert response.status_code == 409
    assert error_code(response) == "formation_closed"


def test_dados_sem_desafio_escolhido(team, leader, project):
    project.challenge = None
    project.save()
    response = client_for(leader).put(url(team, "/details"), DETAILS, format="json")
    assert response.status_code == 409
    assert error_code(response) == "challenge_not_selected"


def test_dados_com_titulo_repetido_na_edicao(team, leader, project):
    ProjectFactory(team=TeamFactory(edition=team.edition), title="ÁGUA LIMPA")
    body = {"title": "água  limpa", "summary": "x"}

    response = client_for(leader).put(url(team, "/details"), body, format="json")

    assert response.status_code == 409
    assert error_code(response) == "project_title_taken"


def test_dados_em_equipe_inexistente(leader):
    response = client_for(leader).put(
        "/api/teams/999999/project/details", DETAILS, format="json"
    )
    assert response.status_code == 404


# Fluxo completo: escolher o desafio e depois cadastrar os dados


def test_fluxo_escolher_e_cadastrar_e_consultar(team, leader, challenge):
    client = client_for(leader)

    client.put(url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json")
    client.put(url(team, "/details"), DETAILS, format="json")
    response = client.get(url(team))

    assert response.status_code == 200
    assert response.data["challenge"]["id"] == challenge.pk
    assert response.data["title"] == "Água limpa"
