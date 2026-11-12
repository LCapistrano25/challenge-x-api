import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    ExternalReviewerFactory,
    StudentFactory,
    TeacherFactory,
    UserFactory,
)
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory

# GET /api/admin/editions e GET /api/admin/editions/{id}: só administrador (RF47)

LIST_URL = "/api/admin/editions"

CONTRACT_FIELDS = {
    "id",
    "year",
    "semester",
    "name",
    "status",
    "notice_url",
    "min_members",
    "max_members",
    "published_at",
    "closed_at",
    "created_at",
    "updated_at",
}


def detail_url(edition):
    return f"{LIST_URL}/{edition.pk}"


@pytest.fixture
def client(db):
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.ADMIN))
    return client


@pytest.fixture
def anonymous_client():
    return APIClient()


# ---------------------------------------------------------------- listagem


def test_lista_devolve_array_simples_com_os_campos_do_contrato(client):
    edition = EditionFactory()

    resposta = client.get(LIST_URL)

    assert resposta.status_code == 200
    assert isinstance(resposta.data, list)
    assert len(resposta.data) == 1
    assert set(resposta.data[0]) == CONTRACT_FIELDS
    assert resposta.data[0]["id"] == edition.pk


def test_lista_vazia_devolve_array_vazio(client):
    resposta = client.get(LIST_URL)

    assert resposta.status_code == 200
    assert resposta.data == []


def test_lista_segue_a_ordem_do_model_ano_e_semestre_decrescentes(client):
    antiga = EditionFactory(year=2024, semester=2)
    recente = EditionFactory(year=2026, semester=1)
    meio = EditionFactory(year=2025, semester=2)
    primeiro_semestre = EditionFactory(year=2025, semester=1)

    resposta = client.get(LIST_URL)

    assert [e["id"] for e in resposta.data] == [
        recente.pk,
        meio.pk,
        primeiro_semestre.pk,
        antiga.pk,
    ]


def test_lista_inclui_edicoes_de_qualquer_status(client):
    for status in EditionStatus:
        EditionFactory(status=status)

    resposta = client.get(LIST_URL)

    assert {e["status"] for e in resposta.data} == {s.value for s in EditionStatus}


@pytest.mark.parametrize(
    "make_user",
    [
        lambda: StudentFactory().user,
        lambda: TeacherFactory().user,
        lambda: ExternalReviewerFactory().user,
    ],
    ids=["aluno", "professor", "avaliador_externo"],
)
def test_lista_recusa_outros_perfis(db, make_user):
    client = APIClient()
    client.force_authenticate(make_user())

    resposta = client.get(LIST_URL)

    assert resposta.status_code == 403


def test_lista_sem_login_e_recusada(anonymous_client):
    resposta = anonymous_client.get(LIST_URL)

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "not_authenticated"


# ---------------------------------------------------------------- consulta


def test_consulta_devolve_a_edicao_com_os_campos_do_contrato(client):
    edition = EditionFactory(year=2026, semester=1, name="Desafio X 2026/1")

    resposta = client.get(detail_url(edition))

    assert resposta.status_code == 200
    assert set(resposta.data) == CONTRACT_FIELDS
    assert resposta.data["id"] == edition.pk
    assert resposta.data["year"] == 2026
    assert resposta.data["semester"] == 1
    assert resposta.data["name"] == "Desafio X 2026/1"
    assert resposta.data["status"] == EditionStatus.SETUP
    assert resposta.data["min_members"] == 3
    assert resposta.data["max_members"] == 5
    assert resposta.data["published_at"] is None
    assert resposta.data["closed_at"] is None


def test_consulta_de_edicao_inexistente_devolve_404(client):
    resposta = client.get(f"{LIST_URL}/999999")

    assert resposta.status_code == 404
    assert resposta.data["error"]["code"] == "not_found"


def test_consulta_recusa_outros_perfis(db):
    edition = EditionFactory()
    client = APIClient()
    client.force_authenticate(StudentFactory().user)

    resposta = client.get(detail_url(edition))

    assert resposta.status_code == 403


def test_consulta_sem_login_e_recusada(anonymous_client, db):
    edition = EditionFactory()

    resposta = anonymous_client.get(detail_url(edition))

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "not_authenticated"


# ---------------------------------------------------------------- mapeamento


def test_notice_url_vem_de_regulation_url(client):
    edition = EditionFactory(regulation_url="https://storage.exemplo.edu.br/2026-1.pdf")

    resposta = client.get(detail_url(edition))

    assert resposta.data["notice_url"] == "https://storage.exemplo.edu.br/2026-1.pdf"
    assert "regulation_url" not in resposta.data


def test_notice_url_vazio_e_devolvido_como_null(client):
    edition = EditionFactory(regulation_url="")

    resposta = client.get(detail_url(edition))

    assert resposta.data["notice_url"] is None


def test_nome_vazio_e_devolvido_como_null_na_consulta(client):
    edition = EditionFactory(name="")

    resposta = client.get(detail_url(edition))

    assert resposta.data["name"] is None


def test_nome_vazio_e_devolvido_como_null_na_lista(client):
    EditionFactory(name="")

    resposta = client.get(LIST_URL)

    assert resposta.data[0]["name"] is None
