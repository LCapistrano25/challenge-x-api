import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import CategoryFactory, EditionFactory
from apps.editions.models import Category
from apps.projects.factories import ProjectFactory
from apps.teams.factories import TeamFactory

pytestmark = pytest.mark.django_db


def url(edition_id):
    return f"/api/admin/editions/{edition_id}/categories"


def detail(category):
    return f"/api/admin/categories/{category.pk}"


@pytest.fixture
def admin_client():
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.ADMIN))
    return client


def test_lista_categorias_da_edicao_conforme_contrato(admin_client):
    first = CategoryFactory(description="Descrição")
    second = CategoryFactory(edition=first.edition, description="", active=False)
    CategoryFactory()

    response = admin_client.get(url(first.edition_id))

    assert response.status_code == 200
    categories = response.json()
    assert [item["id"] for item in categories] == [first.pk, second.pk]
    assert all(mismatches(item, schema("Category")) == [] for item in categories)
    assert categories[0]["description"] == first.description
    assert categories[1]["description"] is None
    assert categories[1]["active"] is False


def test_edicao_sem_categorias_retorna_array_vazio(admin_client):
    response = admin_client.get(url(EditionFactory().pk))
    assert response.status_code == 200
    assert response.json() == []


def test_listagem_de_edicao_inexistente(admin_client):
    edition = EditionFactory()
    path = url(edition.pk)
    edition.delete()

    response = admin_client.get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "role", [None, UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_listagem_restrita_ao_admin(role):
    client = APIClient()
    if role is not None:
        client.force_authenticate(UserFactory(role=role))

    response = client.get(url(EditionFactory().pk))

    assert response.status_code == (401 if role is None else 403)


def test_cadastra_categoria_normalizando_nome_e_descricao(admin_client):
    edition = EditionFactory()
    response = admin_client.post(
        url(edition.pk), {"name": "  Protótipo  ", "description": None}, format="json"
    )
    assert response.status_code == 201
    body = response.json()
    assert mismatches(body, schema("Category")) == []
    category = edition.categories.get()
    assert category.name == body["name"] == "Protótipo"
    assert category.description == ""
    assert body["description"] is None
    assert body["active"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "  "},
        {"name": "A" * 151},
        {"name": "Categoria", "active": "false"},
        {"name": "Categoria", "other": 1},
    ],
)
def test_cadastro_rejeita_payload_invalido(admin_client, payload):
    edition = EditionFactory()
    response = admin_client.post(url(edition.pk), payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert not edition.categories.exists()


def test_nome_duplicado_so_conflita_na_mesma_edicao(admin_client):
    existing = CategoryFactory()
    payload = {"name": f"  {existing.name}  "}
    conflict = admin_client.post(url(existing.edition_id), payload, format="json")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "category_name_taken"
    assert (
        admin_client.post(url(EditionFactory().pk), payload, format="json").status_code
        == 201
    )


def test_cadastro_em_edicao_encerrada(admin_client):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    response = admin_client.post(url(edition.pk), {"name": "Categoria"}, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "edition_closed"


def test_patch_parcial_distingue_descricao_omitida_de_null(admin_client):
    category = CategoryFactory(description="Original")
    response = admin_client.patch(
        detail(category), {"name": "  Revisada  "}, format="json"
    )
    assert response.status_code == 200
    body = response.json()
    assert mismatches(body, schema("Category")) == []
    assert body["name"] == "Revisada"
    assert body["description"] == "Original"

    response = admin_client.patch(
        detail(category), {"description": None}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["description"] is None
    category.refresh_from_db()
    assert category.description == ""


@pytest.mark.parametrize(
    "payload", [{}, {"name": "  "}, {"name": ""}, {"edition_id": 1}]
)
def test_patch_rejeita_payload_invalido(admin_client, payload):
    category = CategoryFactory()
    response = admin_client.patch(detail(category), payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_patch_com_nome_duplicado_nao_aplica_mudancas_parciais(admin_client):
    first = CategoryFactory()
    second = CategoryFactory(edition=first.edition, description="Original")
    response = admin_client.patch(
        detail(second), {"name": first.name, "description": "Revisada"}, format="json"
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "category_name_taken"
    second.refresh_from_db()
    assert second.description == "Original"


def test_exclui_categoria_sem_uso(admin_client):
    category = CategoryFactory()
    response = admin_client.delete(detail(category))
    assert response.status_code == 204
    assert response.content == b""
    assert not category.edition.categories.filter(pk=category.pk).exists()


def test_categoria_em_uso_pode_ser_desativada_mas_nao_excluida(admin_client):
    category = CategoryFactory()
    project = ProjectFactory(
        team=TeamFactory(edition=category.edition), category=category
    )
    response = admin_client.delete(detail(category))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "category_in_use"

    response = admin_client.patch(detail(category), {"active": False}, format="json")
    assert response.status_code == 200
    project.refresh_from_db()
    category.refresh_from_db()
    assert project.category_id == category.pk
    assert category.active is False


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_categoria_em_edicao_encerrada(admin_client, method):
    category = CategoryFactory(edition=EditionFactory(status=EditionStatus.CLOSED))
    response = getattr(admin_client, method)(
        detail(category), {"active": False}, format="json"
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "edition_closed"


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
@pytest.mark.parametrize(
    "role", [None, UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_escrita_restrita_ao_admin(method, role):
    category = CategoryFactory()
    client = APIClient()
    if role is not None:
        client.force_authenticate(UserFactory(role=role))
    path = url(category.edition_id) if method == "post" else detail(category)
    response = getattr(client, method)(path)
    assert response.status_code == (401 if role is None else 403)


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_categoria_inexistente(admin_client, method):
    category = CategoryFactory()
    path = detail(category)
    category.delete()
    response = getattr(admin_client, method)(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_categoria_que_some_entre_busca_e_trava_retorna_404(
    admin_client, method, monkeypatch
):
    category = CategoryFactory()
    path = detail(category)

    def read_before_concurrent_delete(model, *, pk):
        assert model is Category
        assert pk == category.pk
        Category.objects.filter(pk=pk).delete()
        return category

    monkeypatch.setattr(
        "apps.editions.views.get_object_or_404", read_before_concurrent_delete
    )
    response = getattr(admin_client, method)(path, {"active": False}, format="json")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
