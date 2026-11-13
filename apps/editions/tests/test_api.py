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
from apps.editions.models import Edition

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


# ---------------------------------------------------------------- cadastro
# POST /api/admin/editions: ano e semestre obrigatórios, nome opcional (RF47)


@pytest.fixture
def payload():
    return {"year": 2030, "semester": 1, "name": "Desafio X 2030/1"}


def post(client, data):
    return client.post(LIST_URL, data, format="json")


def test_cadastro_devolve_201_com_a_edicao_do_contrato(client, payload):
    resposta = post(client, payload)

    assert resposta.status_code == 201
    assert set(resposta.data) == CONTRACT_FIELDS
    assert resposta.data["year"] == 2030
    assert resposta.data["semester"] == 1
    assert resposta.data["name"] == "Desafio X 2030/1"
    assert resposta.data["status"] == EditionStatus.SETUP
    assert resposta.data["min_members"] == 3
    assert resposta.data["max_members"] == 5
    assert resposta.data["notice_url"] is None
    assert resposta.data["published_at"] is None
    assert resposta.data["closed_at"] is None
    edition = Edition.objects.get(pk=resposta.data["id"])
    assert (edition.year, edition.semester, edition.status) == (
        2030,
        1,
        EditionStatus.SETUP,
    )


def test_cadastro_sem_nome_grava_vazio_e_devolve_null(client):
    resposta = post(client, {"year": 2030, "semester": 2})

    assert resposta.status_code == 201
    assert resposta.data["name"] is None
    assert Edition.objects.get(pk=resposta.data["id"]).name == ""


@pytest.mark.parametrize("name", [None, ""], ids=["null", "vazio"])
def test_cadastro_com_nome_null_ou_vazio_grava_vazio(client, name):
    resposta = post(client, {"year": 2030, "semester": 2, "name": name})

    assert resposta.status_code == 201
    assert resposta.data["name"] is None
    assert Edition.objects.get(pk=resposta.data["id"]).name == ""


def test_cadastro_aceita_nome_com_100_caracteres(client, payload):
    payload["name"] = "x" * 100

    assert post(client, payload).status_code == 201


def test_cadastro_com_nome_de_101_caracteres_e_recusado(client, payload):
    payload["name"] = "x" * 101

    resposta = post(client, payload)

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert "name" in resposta.data["error"]["details"]
    assert not Edition.objects.exists()


@pytest.mark.parametrize("missing", ["year", "semester"])
def test_cadastro_exige_ano_e_semestre(client, payload, missing):
    del payload[missing]

    resposta = post(client, payload)

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert missing in resposta.data["error"]["details"]
    assert not Edition.objects.exists()


@pytest.mark.parametrize("semester", [0, 3, -1, "a", None, 1.5])
def test_cadastro_recusa_semestre_invalido(client, payload, semester):
    payload["semester"] = semester

    resposta = post(client, payload)

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert "semester" in resposta.data["error"]["details"]
    assert not Edition.objects.exists()


@pytest.mark.parametrize("year", [0, -2026, 32768, "abc", None])
def test_cadastro_recusa_ano_invalido(client, payload, year):
    payload["year"] = year

    resposta = post(client, payload)

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert "year" in resposta.data["error"]["details"]
    assert not Edition.objects.exists()


@pytest.mark.parametrize(
    "extra",
    [
        {"status": "PUBLISHED"},
        {"min_members": 2},
        {"id": 99},
        {"notice_url": "https://exemplo.edu.br/a.pdf"},
    ],
    ids=["status", "limites", "id", "notice_url"],
)
def test_cadastro_recusa_campos_desconhecidos(client, payload, extra):
    payload.update(extra)

    resposta = post(client, payload)

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert set(extra) <= set(resposta.data["error"]["details"])
    assert not Edition.objects.exists()


def test_cadastro_recusa_corpo_que_nao_e_objeto(client):
    resposta = post(client, [])

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"


def test_cadastro_de_edicao_duplicada_devolve_409(client, payload):
    EditionFactory(year=2030, semester=1)

    resposta = post(client, payload)

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "edition_exists"
    assert Edition.objects.count() == 1


def test_cadastro_do_outro_semestre_do_mesmo_ano_e_permitido(client, payload):
    EditionFactory(year=2030, semester=2)

    assert post(client, payload).status_code == 201


@pytest.mark.parametrize(
    "make_user",
    [
        lambda: StudentFactory().user,
        lambda: TeacherFactory().user,
        lambda: ExternalReviewerFactory().user,
    ],
    ids=["aluno", "professor", "avaliador_externo"],
)
def test_cadastro_recusa_outros_perfis(db, payload, make_user):
    client = APIClient()
    client.force_authenticate(make_user())

    resposta = post(client, payload)

    assert resposta.status_code == 403
    assert not Edition.objects.exists()


def test_cadastro_sem_login_e_recusado(db, anonymous_client, payload):
    resposta = post(anonymous_client, payload)

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "not_authenticated"
    assert not Edition.objects.exists()
