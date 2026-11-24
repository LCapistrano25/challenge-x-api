import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, TeacherFactory, UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.projects.factories import ProjectFactory
from apps.teams.enums import TeamSituation, TeamStatus
from apps.teams.factories import TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db

TEAMS_URL = "/api/admin/teams"


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


def test_listagem_administrativa_requer_autenticacao():
    response = APIClient().get(TEAMS_URL)

    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"


@pytest.mark.parametrize("user_factory", [StudentFactory, TeacherFactory])
def test_listagem_administrativa_rejeita_usuario_sem_permissao(user_factory):
    user = user_factory().user

    response = authenticated_client(user).get(TEAMS_URL)

    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"


def test_admin_lista_equipes_da_edicao_publicada(admin):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition, situation=TeamSituation.COMPLETE)
    TeamMemberFactory(team=team, role="MEMBER")

    response = authenticated_client(admin).get(TEAMS_URL)

    assert response.data["count"] == 1
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] == team.id
    assert response.data["results"][0]["edition_id"] == edition.id
    assert response.data["results"][0]["situation"] == TeamSituation.COMPLETE
    assert response.data["results"][0]["member_count"] == 2


def test_listagem_inclui_equipes_desclassificadas(admin):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition, disqualified=True)

    response = authenticated_client(admin).get(TEAMS_URL)

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] == team.id
    assert response.data["results"][0]["status"] == TeamStatus.DISQUALIFIED


def test_listagem_nao_inclui_equipes_de_edicoes_nao_publicadas(admin):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    TeamFactory(edition=edition)

    response = authenticated_client(admin).get(TEAMS_URL)

    assert response.status_code == 200
    assert response.data["count"] == 0
    assert response.data["results"] == []
    assert response.data["next"] is None
    assert response.data["previous"] is None


def test_desclassificacao_administrativa_requer_autenticacao():
    response = APIClient().post(
        f"{TEAMS_URL}/1/disqualify",
        {"reason": "Descumprimento do edital."},
        format="json",
    )

    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"


def test_admin_desclassifica_equipe_com_justificativa(admin):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)

    response = authenticated_client(admin).post(
        f"{TEAMS_URL}/{team.id}/disqualify",
        {"reason": "Descumprimento do edital."},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["id"] == team.id
    assert response.data["status"] == TeamStatus.DISQUALIFIED
    assert len(response.data["members"]) == 1
    assert response.data["situation"] == team.situation
    assert response.data["disqualification_reason"] == "Descumprimento do edital."
    assert response.data["disqualified_at"] is not None
    assert response.data["disqualified_by"] == admin.id

    team.refresh_from_db()

    assert team.status == TeamStatus.DISQUALIFIED
    assert team.disqualification_reason == "Descumprimento do edital."
    assert team.disqualified_by == admin
    assert team.disqualified_at is not None


def test_desclassificacao_rejeita_usuario_sem_permissao():
    team = TeamFactory(edition=EditionFactory(status=EditionStatus.PUBLISHED))
    student = StudentFactory()

    response = authenticated_client(student.user).post(
        f"{TEAMS_URL}/{team.id}/disqualify",
        {"reason": "Descumprimento do edital."},
        format="json",
    )

    assert response.status_code == 403
    team.refresh_from_db()
    assert team.status == TeamStatus.ACTIVE


def test_desclassificacao_sem_justificativa_retorna_400(admin):
    team = TeamFactory(edition=EditionFactory(status=EditionStatus.PUBLISHED))

    response = authenticated_client(admin).post(
        f"{TEAMS_URL}/{team.id}/disqualify",
        {"reason": "   "},
        format="json",
    )

    assert response.status_code == 400
    team.refresh_from_db()
    assert team.status == TeamStatus.ACTIVE


def test_desclassificacao_de_equipe_inexistente_retorna_404(admin):
    response = authenticated_client(admin).post(
        f"{TEAMS_URL}/999999/disqualify",
        {"reason": "Descumprimento do edital."},
        format="json",
    )

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"


def test_listagem_filtra_por_edicao(admin):
    edition_1 = EditionFactory(status=EditionStatus.PUBLISHED)
    edition_2 = EditionFactory(status=EditionStatus.PUBLISHED)

    team_1 = TeamFactory(edition=edition_1)
    TeamFactory(edition=edition_2)

    response = authenticated_client(admin).get(
        TEAMS_URL,
        {"edition_id": edition_1.id},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == team_1.id


def test_listagem_filtra_por_status(admin):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    active_team = TeamFactory(edition=edition)
    TeamFactory(edition=edition, disqualified=True)

    response = authenticated_client(admin).get(
        TEAMS_URL,
        {"status": TeamStatus.ACTIVE},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == active_team.id


@pytest.mark.parametrize(
    "search_term",
    [
        "Equipe Busca",
        "BUSCA123",
        "irrigação inteligente",
    ],
)
def test_listagem_busca_por_nome_codigo_ou_projeto(admin, search_term):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    team = TeamFactory(
        edition=edition,
        name="Equipe Busca Especial",
        code="BUSCA123",
    )
    ProjectFactory(
        team=team,
        title="Sistema de irrigação inteligente",
    )

    TeamFactory(edition=edition)

    response = authenticated_client(admin).get(
        TEAMS_URL,
        {"search": search_term},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == team.id


def test_listagem_retorna_resultados_paginados(admin):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    TeamFactory.create_batch(21, edition=edition)

    response = authenticated_client(admin).get(TEAMS_URL)

    assert response.status_code == 200
    assert response.data["count"] == 21
    assert len(response.data["results"]) == 20
    assert response.data["next"] is not None
    assert response.data["previous"] is None

    next_page = authenticated_client(admin).get(
        TEAMS_URL,
        {"page": 2},
    )

    assert next_page.status_code == 200
    assert len(next_page.data["results"]) == 1
    assert next_page.data["previous"] is not None


def test_desclassificacao_de_equipe_ja_desclassificada_retorna_409(admin):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition, disqualified=True)

    response = authenticated_client(admin).post(
        f"{TEAMS_URL}/{team.id}/disqualify",
        {"reason": "Nova justificativa."},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "team_already_disqualified"

    team.refresh_from_db()
    assert team.status == TeamStatus.DISQUALIFIED


def test_desclassificacao_de_equipe_com_edicao_encerrada_retorna_409(admin):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    team = TeamFactory(edition=edition)

    response = authenticated_client(admin).post(
        f"{TEAMS_URL}/{team.id}/disqualify",
        {"reason": "Descumprimento do edital."},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "edition_closed"

    team.refresh_from_db()
    assert team.status == TeamStatus.ACTIVE
