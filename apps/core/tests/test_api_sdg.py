import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Sdg
from apps.editions.factories import ChallengeFactory


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


@pytest.mark.django_db
@pytest.mark.parametrize("field,size", [("title", 201), ("icon", 101)])
def test_api_update_sdg_field_too_long_returns_400(api_client, admin_user, field, size):
    """Testa se texto acima do limite da coluna retorna 400, e não 500."""
    sdg = Sdg.objects.first()
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(
        f"/api/admin/sdgs/{sdg.pk}", data={field: "a" * size}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.data["error"]["details"]


@pytest.mark.django_db
def test_api_admin_sdg_response_has_timestamps(api_client, admin_user):
    """Testa se a ODS do admin traz created_at e updated_at, como o schema Sdg."""
    sdg = Sdg.objects.first()
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(
        f"/api/admin/sdgs/{sdg.pk}", data={"active": False}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert {"created_at", "updated_at"} <= response.data.keys()


@pytest.mark.django_db
def test_api_create_sdg_duplicate_number_returns_409(api_client, admin_user):
    """Número repetido volta 409 sdg_number_taken, como no contrato (#281)."""
    api_client.force_authenticate(user=admin_user)
    number = Sdg.objects.first().number

    response = api_client.post(
        "/api/admin/sdgs", data={"number": number, "title": "Duplicada"}
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "sdg_number_taken"


@pytest.mark.django_db
def test_api_delete_sdg_in_use_returns_409(api_client, admin_user):
    """ODS usada por desafio volta 409 sdg_in_use, não 500 (#280)."""
    api_client.force_authenticate(user=admin_user)
    sdg = Sdg.objects.first()
    ChallengeFactory(sdg=sdg)

    response = api_client.delete(f"/api/admin/sdgs/{sdg.id}")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "sdg_in_use"


@pytest.mark.django_db
def test_api_delete_sdg_not_found_returns_404(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)

    response = api_client.delete("/api/admin/sdgs/999999")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_api_list_admin_sdgs_filters_by_active(api_client, admin_user):
    """O filtro active separa ativas de inativas (#282)."""
    api_client.force_authenticate(user=admin_user)
    inactive = Sdg.objects.first()
    inactive.active = False
    inactive.save()

    response = api_client.get("/api/admin/sdgs?active=false")

    assert response.status_code == status.HTTP_200_OK
    assert [s["id"] for s in response.data] == [inactive.id]


@pytest.mark.django_db
def test_api_list_admin_sdgs_invalid_active_returns_400(api_client, admin_user):
    """Filtro active inválido volta 400 validation_error (#282)."""
    api_client.force_authenticate(user=admin_user)

    response = api_client.get("/api/admin/sdgs?active=talvez")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "validation_error"
    assert "active" in response.data["error"]["details"]


@pytest.mark.django_db
def test_api_create_sdg_without_number_and_title_returns_400(api_client, admin_user):
    """Testa se o POST sem number e title responde 400, e não 500."""
    api_client.force_authenticate(user=admin_user)

    response = api_client.post("/api/admin/sdgs", data={}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert {"number", "title"} <= response.data["error"]["details"].keys()


@pytest.mark.django_db
def test_api_update_sdg_without_fields_returns_400(api_client, admin_user):
    """Testa se o PATCH sem nenhum campo responde 400 (contrato: minProperties 1)."""
    sdg = Sdg.objects.first()
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(f"/api/admin/sdgs/{sdg.pk}", data={}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
