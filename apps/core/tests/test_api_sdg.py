import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Sdg


@pytest.fixture
def api_client():
    """Fornece o cliente de testes da API."""
    return APIClient()


@pytest.mark.django_db
def test_api_list_public_sdgs(api_client):
    """Testa se o GET público de ODS retorna 200 OK sem autenticação."""
    response = api_client.get("/api/sdgs")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data, list)


@pytest.mark.django_db
def test_api_list_admin_sdgs(api_client, admin_user):
    """Testa se o GET admin de ODS retorna 200 OK."""
    api_client.force_authenticate(user=admin_user)
    response = api_client.get("/api/admin/sdgs")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_api_create_sdg(api_client, admin_user):
    """Testa se o POST admin cadastra ODS com 201 Created."""
    Sdg.objects.all().delete()  # Limpa as ODS iniciais para evitar conflito de número
    api_client.force_authenticate(user=admin_user)

    payload = {"number": 4, "title": "Educação de Qualidade"}
    response = api_client.post("/api/admin/sdgs", data=payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "Educação de Qualidade"


@pytest.mark.django_db
def test_api_update_sdg(api_client, admin_user):
    """Testa se o PATCH admin atualiza ODS com 200 OK."""
    api_client.force_authenticate(user=admin_user)
    sdg = Sdg.objects.first()

    payload = {"title": "Título Atualizado API"}
    response = api_client.patch(f"/api/admin/sdgs/{sdg.id}", data=payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["title"] == "Título Atualizado API"


@pytest.mark.django_db
def test_api_delete_sdg(api_client, admin_user):
    """Testa se o DELETE admin exclui ODS com 204 No Content."""
    api_client.force_authenticate(user=admin_user)
    sdg = Sdg.objects.first()

    response = api_client.delete(f"/api/admin/sdgs/{sdg.id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
