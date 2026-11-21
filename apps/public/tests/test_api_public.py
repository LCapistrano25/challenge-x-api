import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.editions.factories import EditionFactory
from apps.projects.enums import ProjectStatus
from apps.projects.factories import ProjectFactory
from apps.results.factories import ProjectResultFactory


@pytest.fixture
def api_client():
    """Fornece o cliente de testes da API."""
    return APIClient()


@pytest.mark.django_db
def test_api_current_edition_success(api_client):
    """Testa se o endpoint devolve 200 OK com a edição vigente."""
    now = timezone.now()
    vigente = EditionFactory(published_at=now, closed_at=None)

    response = api_client.get("/api/public/editions/current")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == vigente.id


@pytest.mark.django_db
def test_api_current_edition_not_found(api_client):
    """Testa se o endpoint devolve 404 quando não há edição vigente."""
    response = api_client.get("/api/public/editions/current")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_api_closed_editions_list(api_client):
    """Testa se o endpoint devolve 200 OK com a lista de edições encerradas."""
    now = timezone.now()
    EditionFactory(published_at=now, closed_at=now)
    EditionFactory(published_at=now, closed_at=now)

    response = api_client.get("/api/public/editions")

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2


@pytest.mark.django_db
def test_api_edition_winners_list(api_client):
    """Testa se o endpoint devolve 200 OK com os vencedores da edição."""
    edicao = EditionFactory()
    proj = ProjectFactory(edition=edicao)
    ProjectResultFactory(project=proj, award=1, final_score=9.50)

    response = api_client.get(f"/api/public/editions/{edicao.id}/winners")

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["award"] == 1
    assert response.data[0]["project_id"] == proj.id


@pytest.mark.django_db
def test_api_public_projects_list(api_client):
    """Testa se a vitrine retorna 200 OK apenas com projetos COMPLETED."""
    ProjectFactory(status=ProjectStatus.COMPLETED)
    ProjectFactory(status=ProjectStatus.IN_PROGRESS)

    response = api_client.get("/api/public/projects")

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1


@pytest.mark.django_db
def test_api_public_project_detail_success(api_client):
    """Testa se o detalhe de um projeto COMPLETED retorna 200 OK."""
    proj = ProjectFactory(status=ProjectStatus.COMPLETED)

    response = api_client.get(f"/api/public/projects/{proj.id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == proj.id


@pytest.mark.django_db
def test_api_public_project_detail_not_found(api_client):
    """Testa se o detalhe de um projeto não concluído retorna 404."""
    proj = ProjectFactory(status=ProjectStatus.IN_PROGRESS)

    response = api_client.get(f"/api/public/projects/{proj.id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
