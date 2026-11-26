"""GET /api/teams/{team_id}/invitable-students (#232)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.factories import StudentFactory
from apps.core.tests.contract import mismatches, schema
from apps.teams.factories import InvitationFactory, TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db


def url(team, search="Mar"):
    return f"/api/teams/{team.pk}/invitable-students?search={search}"


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def leader_of(team):
    return team.members.get(role="LEADER", active=True).student.user


def student(name, **kwargs):
    return StudentFactory(user__name=name, **kwargs)


def names(response):
    return [s["name"] for s in response.json()["results"]]


def test_lista_alunos_que_podem_ser_convidados_e_segue_o_contrato():
    team = TeamFactory()
    maria = student("Maria Souza")
    student("Mariana Lima")
    student("João Pereira")

    response = client_for(leader_of(team)).get(url(team))

    assert response.status_code == 200
    assert mismatches(response.json(), schema("PaginatedInvitableStudent")) == []
    # A ordem por nome segue a collation do banco; aqui basta o conjunto.
    assert set(names(response)) == {"Maria Souza", "Mariana Lima"}
    [row] = [r for r in response.json()["results"] if r["id"] == maria.pk]
    assert row == {
        "id": maria.pk,
        "name": "Maria Souza",
        "course": {"id": maria.course_id, "name": maria.course.name},
    }


def test_fica_de_fora_quem_nao_pode_receber_convite():
    team = TeamFactory()
    student("Maria Ativa")
    student("Maria Inativa", user__is_active=False)
    student("Maria Sem Confirmar", user__email_confirmed=False)
    TeamMemberFactory(
        team=TeamFactory(edition=team.edition), student=student("Maria Com Equipe")
    )
    InvitationFactory(team=team, student=student("Maria Convidada"))

    response = client_for(leader_of(team)).get(url(team))

    assert names(response) == ["Maria Ativa"]


def test_aluno_de_equipe_de_outra_edicao_aparece():
    team = TeamFactory()
    TeamMemberFactory(team=TeamFactory(), student=student("Maria Outra Edicao"))

    response = client_for(leader_of(team)).get(url(team))

    assert names(response) == ["Maria Outra Edicao"]


@pytest.mark.parametrize("search", ["", "Ma", "%20%20Ma%20%20"])
def test_busca_exige_3_caracteres(search):
    team = TeamFactory()

    response = client_for(leader_of(team)).get(url(team, search))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "search" in response.json()["error"]["details"]


def test_busca_obrigatoria():
    team = TeamFactory()

    response = client_for(leader_of(team)).get(
        f"/api/teams/{team.pk}/invitable-students"
    )

    assert response.status_code == 400


def test_integrante_que_nao_e_lider_recebe_403():
    team = TeamFactory()
    member = TeamMemberFactory(team=team)

    response = client_for(member.student.user).get(url(team))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_team_leader"


def test_equipe_inexistente_recebe_404():
    team = TeamFactory()

    response = client_for(leader_of(team)).get(
        "/api/teams/999999/invitable-students?search=Mar"
    )

    assert response.status_code == 404


def test_sem_login_recebe_401():
    assert APIClient().get(url(TeamFactory())).status_code == 401
