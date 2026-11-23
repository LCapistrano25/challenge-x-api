import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, TeacherFactory, UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
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

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == team.id
    assert response.data[0]["edition_id"] == edition.id
    assert response.data[0]["situation"] == TeamSituation.COMPLETE
    assert response.data[0]["active_members_count"] == 2


def test_listagem_inclui_equipes_desclassificadas(admin):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition, disqualified=True)

    response = authenticated_client(admin).get(TEAMS_URL)

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == team.id
    assert response.data[0]["status"] == TeamStatus.DISQUALIFIED
    assert response.data[0]["disqualification_reason"] == (
        team.disqualification_reason
    )


def test_listagem_nao_inclui_equipes_de_edicoes_nao_publicadas(admin):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    TeamFactory(edition=edition)

    response = authenticated_client(admin).get(TEAMS_URL)

    assert response.status_code == 200
    assert response.data == []


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
    assert response.data["active_members_count"] == 1
    assert response.data["disqualification_reason"] == "Descumprimento do edital."
    assert response.data["disqualified_by_id"] == admin.id
    assert response.data["disqualified_at"] is not None

    team.refresh_from_db()
    assert team.status == TeamStatus.DISQUALIFIED
    assert team.disqualification_reason == "Descumprimento do edital."
    assert team.disqualified_by == admin
    assert team.disqualified_at is not None


def test_desclassificacao_rejeita_usuario_sem_permissao():
    team = TeamFactory(
        edition=EditionFactory(status=EditionStatus.PUBLISHED)
    )
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
    team = TeamFactory(
        edition=EditionFactory(status=EditionStatus.PUBLISHED)
    )

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
