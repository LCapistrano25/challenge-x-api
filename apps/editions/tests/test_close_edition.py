"""UC18 — encerrar a edição (RF47, P-16, P-26, P-45)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionAlreadyClosed, EditionNotPublished
from apps.editions.factories import EditionFactory
from apps.editions.use_cases.close_edition import close_edition
from apps.projects.enums import ProjectStatus
from apps.projects.factories import ProjectFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def edition():
    return EditionFactory(status=EditionStatus.PUBLISHED)


def project_in(edition, status):
    project = ProjectFactory(team__edition=edition)
    project.status = status
    project.save(update_fields=["status"])
    return project


# Caso de uso


def test_encerra_e_conclui_projetos_nao_desclassificados(admin, edition):
    in_progress = project_in(edition, ProjectStatus.IN_PROGRESS)
    disqualified = project_in(edition, ProjectStatus.DISQUALIFIED)
    other_edition = project_in(
        EditionFactory(status=EditionStatus.PUBLISHED), ProjectStatus.IN_PROGRESS
    )

    closed = close_edition(actor=admin, edition=edition)

    edition.refresh_from_db()
    assert edition.status == closed.status == EditionStatus.CLOSED
    assert edition.closed_at is not None
    for project, expected in [
        (in_progress, ProjectStatus.COMPLETED),
        (disqualified, ProjectStatus.DISQUALIFIED),
        (other_edition, ProjectStatus.IN_PROGRESS),
    ]:
        project.refresh_from_db()
        assert project.status == expected


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (EditionStatus.SETUP, EditionNotPublished),
        (EditionStatus.CLOSED, EditionAlreadyClosed),
    ],
)
def test_so_encerra_edicao_publicada(admin, status, error):
    edition = EditionFactory(status=status)
    project = project_in(edition, ProjectStatus.IN_PROGRESS)

    with pytest.raises(error):
        close_edition(actor=admin, edition=edition)

    edition.refresh_from_db()
    project.refresh_from_db()
    assert edition.status == status
    assert project.status == ProjectStatus.IN_PROGRESS


def test_exige_admin(edition):
    with pytest.raises(NotAdminActor):
        close_edition(actor=UserFactory(role=UserRole.TEACHER), edition=edition)

    edition.refresh_from_db()
    assert edition.status == EditionStatus.PUBLISHED


# API


def url(edition_id):
    return f"/api/admin/editions/{edition_id}/close"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_post_segue_o_contrato(admin, edition):
    body = {"confirm": True}
    assert mismatches(body, schema("EditionClose")) == []

    response = client_for(admin).post(url(edition.pk), body, format="json")

    assert response.status_code == 200
    data = response.json()
    assert mismatches(data, schema("Edition")) == []
    assert data["status"] == "CLOSED"
    assert data["closed_at"] is not None


@pytest.mark.parametrize(
    "body",
    [{}, {"confirm": False}, {"confirm": "true"}, {"confirm": True, "extra": 1}],
)
def test_corpo_fora_do_contrato_responde_400(admin, edition, body):
    response = client_for(admin).post(url(edition.pk), body, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    edition.refresh_from_db()
    assert edition.status == EditionStatus.PUBLISHED


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (EditionStatus.SETUP, "edition_not_published"),
        (EditionStatus.CLOSED, "edition_already_closed"),
    ],
)
def test_conflitos_respondem_409(admin, status, code):
    edition = EditionFactory(status=status)

    response = client_for(admin).post(url(edition.pk), {"confirm": True}, format="json")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == code


def test_edicao_inexistente_responde_404(admin):
    response = client_for(admin).post(url(999999), {"confirm": True}, format="json")

    assert response.status_code == 404


def test_sem_login_401_e_papel_errado_403(edition):
    anonymous = APIClient().post(url(edition.pk), {"confirm": True}, format="json")
    teacher = client_for(UserFactory(role=UserRole.TEACHER)).post(
        url(edition.pk), {"confirm": True}, format="json"
    )

    assert anonymous.status_code == 401
    assert teacher.status_code == 403
