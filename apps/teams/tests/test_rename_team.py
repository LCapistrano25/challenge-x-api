"""PATCH /api/teams/{team_id}: editar o nome da equipe (#233)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.factories import StageFactory
from apps.teams.enums import TeamStatus
from apps.teams.factories import TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db


def open_formation(edition):
    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )


@pytest.fixture
def team():
    team = TeamFactory(name="Equipe Antiga")
    open_formation(team.edition)
    return team


def leader_of(team):
    return team.members.get(role="LEADER", active=True).student.user


def patch(user, team, body):
    client = APIClient()
    if user is not None:
        client.force_login(user)
    return client.patch(f"/api/teams/{team.pk}", body, format="json")


def error_code(response):
    return response.json()["error"]["code"]


def test_lider_troca_o_nome_e_a_resposta_segue_o_contrato(team):
    body = {"name": "  Equipe Nova  "}
    assert mismatches({"name": "Equipe Nova"}, schema("TeamUpdate")) == []

    response = patch(leader_of(team), team, body)

    assert response.status_code == 200
    assert mismatches(response.json(), schema("Team")) == []
    assert response.json()["name"] == "Equipe Nova"
    team.refresh_from_db()
    assert team.name == "Equipe Nova"


def test_integrante_que_nao_e_lider_recebe_403(team):
    member = TeamMemberFactory(team=team)

    response = patch(member.student.user, team, {"name": "Outra"})

    assert response.status_code == 403
    assert error_code(response) == "not_team_leader"


def test_equipe_inexistente_recebe_404(team):
    class Missing:
        pk = 999999

    assert patch(leader_of(team), Missing, {"name": "Outra"}).status_code == 404


def test_fora_da_formacao_recebe_409():
    team = TeamFactory()  # sem etapa de formação aberta

    response = patch(leader_of(team), team, {"name": "Outra"})

    assert response.status_code == 409
    assert error_code(response) == "formation_closed"


def test_equipe_desclassificada_nao_edita(team):
    type(team).objects.filter(pk=team.pk).update(
        status=TeamStatus.DISQUALIFIED,
        disqualification_reason="Plágio.",
        disqualified_at=timezone.now(),
        disqualified_by=UserFactory(role=UserRole.ADMIN),
    )

    response = patch(leader_of(team), team, {"name": "Outra"})

    assert response.status_code == 409
    assert error_code(response) == "team_disqualified"


def test_nome_de_outra_equipe_da_edicao_recebe_409(team):
    TeamFactory(edition=team.edition, name="Equipe Ocupada")

    response = patch(leader_of(team), team, {"name": "Equipe Ocupada"})

    assert response.status_code == 409
    assert error_code(response) == "team_name_taken"


def test_nome_de_equipe_desfeita_fica_livre(team):
    TeamFactory(edition=team.edition, name="Equipe Livre", status=TeamStatus.DISBANDED)

    assert patch(leader_of(team), team, {"name": "Equipe Livre"}).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 151},
        {"name": "A", "description": "x"},
    ],
)
def test_corpo_invalido_recebe_400(team, body):
    response = patch(leader_of(team), team, body)

    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_sem_login_recebe_401(team):
    assert patch(None, team, {"name": "Outra"}).status_code == 401
