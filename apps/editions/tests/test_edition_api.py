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
    "regulation_url",
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

    assert resposta.status_code == 401
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

    assert resposta.status_code == 401
    assert resposta.data["error"]["code"] == "not_authenticated"


# ---------------------------------------------------------------- mapeamento


def test_detalhe_expoe_regulation_url(client):
    edition = EditionFactory(regulation_url="https://storage.exemplo.edu.br/2026-1.pdf")

    resposta = client.get(detail_url(edition))

    assert (
        resposta.data["regulation_url"] == "https://storage.exemplo.edu.br/2026-1.pdf"
    )
    assert "notice_url" not in resposta.data


def test_regulation_url_vazio_e_devolvido_como_null(client):
    edition = EditionFactory(regulation_url="")

    resposta = client.get(detail_url(edition))

    assert resposta.data["regulation_url"] is None


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
    assert resposta.data["regulation_url"] is None
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
        {"regulation_url": "https://exemplo.edu.br/a.pdf"},
    ],
    ids=["status", "limites", "id", "regulation_url"],
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

    assert resposta.status_code == 401
    assert resposta.data["error"]["code"] == "not_authenticated"
    assert not Edition.objects.exists()


# ---------------------------------------------------------------- atualização
# PATCH /api/admin/editions/{id}: nome e limites, parcial (RF47, RF48)


def patch(client, edition, data):
    return client.patch(detail_url(edition), data, format="json")


def estado(edition):
    edition.refresh_from_db()
    return edition.name, edition.min_members, edition.max_members, edition.status


@pytest.fixture
def edicao(db):
    return EditionFactory(name="Desafio X 2030/1")


def test_atualizacao_devolve_200_com_a_edicao_do_contrato(client, edicao):
    resposta = patch(
        client, edicao, {"name": "Novo nome", "min_members": 2, "max_members": 6}
    )

    assert resposta.status_code == 200
    assert set(resposta.data) == CONTRACT_FIELDS
    assert resposta.data["id"] == edicao.pk
    assert resposta.data["name"] == "Novo nome"
    assert resposta.data["min_members"] == 2
    assert resposta.data["max_members"] == 6
    assert estado(edicao) == ("Novo nome", 2, 6, EditionStatus.SETUP)


def test_atualizacao_sem_nome_nao_o_modifica(client, edicao):
    resposta = patch(client, edicao, {"min_members": 2})

    assert resposta.status_code == 200
    assert resposta.data["name"] == "Desafio X 2030/1"
    assert estado(edicao) == ("Desafio X 2030/1", 2, 5, EditionStatus.SETUP)


@pytest.mark.parametrize("name", [None, ""], ids=["null", "vazio"])
def test_atualizacao_com_nome_null_ou_vazio_limpa_o_nome(client, edicao, name):
    resposta = patch(client, edicao, {"name": name})

    assert resposta.status_code == 200
    assert resposta.data["name"] is None
    assert estado(edicao)[0] == ""


def test_atualizacao_aceita_nome_com_100_caracteres(client, edicao):
    resposta = patch(client, edicao, {"name": "x" * 100})

    assert resposta.status_code == 200
    assert estado(edicao)[0] == "x" * 100


def test_atualizacao_com_nome_de_101_caracteres_e_recusada(client, edicao):
    resposta = patch(client, edicao, {"name": "x" * 101})

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert "name" in resposta.data["error"]["details"]
    assert estado(edicao)[0] == "Desafio X 2030/1"


@pytest.mark.parametrize(
    ("campos", "esperado"),
    [
        ({"min_members": 4}, (4, 5)),
        ({"max_members": 4}, (3, 4)),
        ({"min_members": 5}, (5, 5)),
        ({"max_members": 3}, (3, 3)),
    ],
)
def test_atualizacao_parcial_de_limites_preserva_o_outro(
    client, edicao, campos, esperado
):
    resposta = patch(client, edicao, campos)

    assert resposta.status_code == 200
    assert (resposta.data["min_members"], resposta.data["max_members"]) == esperado
    assert estado(edicao)[1:3] == esperado


@pytest.mark.parametrize("campo", ["min_members", "max_members"])
@pytest.mark.parametrize("valor", ["abc", "3.5", 3.5, None, [], {}, True, 0, -1, 32768])
def test_atualizacao_recusa_limite_que_nao_e_inteiro_valido(
    client, edicao, campo, valor
):
    resposta = patch(client, edicao, {campo: valor})

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert campo in resposta.data["error"]["details"]
    assert estado(edicao) == ("Desafio X 2030/1", 3, 5, EditionStatus.SETUP)


@pytest.mark.parametrize(
    "campos",
    [
        {"min_members": 6},
        {"max_members": 2},
        {"min_members": 6, "max_members": 5},
    ],
)
def test_atualizacao_com_limites_invalidos_em_configuracao_devolve_400(
    client, edicao, campos
):
    resposta = patch(client, edicao, {"name": "Não deve gravar", **campos})

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "invalid_team_limits"
    assert estado(edicao) == ("Desafio X 2030/1", 3, 5, EditionStatus.SETUP)


def test_atualizacao_com_corpo_vazio_e_recusada(client, edicao):
    resposta = patch(client, edicao, {})

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert estado(edicao) == ("Desafio X 2030/1", 3, 5, EditionStatus.SETUP)


@pytest.mark.parametrize(
    "extra",
    [
        {"year": 2031},
        {"semester": 2},
        {"status": "PUBLISHED"},
        {"id": 99},
        {"regulation_url": "https://exemplo.edu.br/a.pdf"},
        {"qualquer": 1},
    ],
    ids=["year", "semester", "status", "id", "regulation_url", "desconhecido"],
)
def test_atualizacao_recusa_campos_desconhecidos_ou_proibidos(client, edicao, extra):
    resposta = patch(client, edicao, {"name": "Não deve gravar", **extra})

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert set(extra) <= set(resposta.data["error"]["details"])
    assert estado(edicao) == ("Desafio X 2030/1", 3, 5, EditionStatus.SETUP)


@pytest.mark.parametrize(
    "corpo", [[], "texto", 1, None], ids=["lista", "str", "int", "null"]
)
def test_atualizacao_recusa_corpo_que_nao_e_objeto(client, edicao, corpo):
    resposta = patch(client, edicao, corpo)

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert estado(edicao) == ("Desafio X 2030/1", 3, 5, EditionStatus.SETUP)


def test_atualizacao_nao_altera_ano_e_semestre(client):
    edicao = EditionFactory(year=2031, semester=2, name="a")

    patch(client, edicao, {"name": "b", "min_members": 2})

    edicao.refresh_from_db()
    assert (edicao.year, edicao.semester) == (2031, 2)


# Estados


def test_publicada_aceita_mudar_so_o_nome(client):
    edicao = EditionFactory(name="Publicada", status=EditionStatus.PUBLISHED)

    resposta = patch(client, edicao, {"name": "Renomeada"})

    assert resposta.status_code == 200
    assert resposta.data["status"] == "PUBLISHED"
    assert estado(edicao) == ("Renomeada", 3, 5, EditionStatus.PUBLISHED)


@pytest.mark.parametrize(
    "campos",
    [
        {"min_members": 2},
        {"max_members": 6},
        {"min_members": 2, "max_members": 6},
        {"min_members": 3, "max_members": 5},
    ],
)
def test_publicada_com_qualquer_limite_devolve_409_sem_alteracao_parcial(
    client, campos
):
    edicao = EditionFactory(name="Publicada", status=EditionStatus.PUBLISHED)

    resposta = patch(client, edicao, {"name": "Não deve gravar", **campos})

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "team_limits_locked"
    assert estado(edicao) == ("Publicada", 3, 5, EditionStatus.PUBLISHED)


@pytest.mark.parametrize(
    "campos",
    [
        {"name": "Novo"},
        {"name": None},
        {"min_members": 2},
        {"name": "Novo", "min_members": 2, "max_members": 6},
    ],
)
def test_encerrada_recusa_qualquer_atualizacao_com_409(client, campos):
    edicao = EditionFactory(name="Encerrada", status=EditionStatus.CLOSED)

    resposta = patch(client, edicao, campos)

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "edition_closed"
    assert estado(edicao) == ("Encerrada", 3, 5, EditionStatus.CLOSED)


# Acesso


@pytest.mark.parametrize(
    "make_user",
    [
        lambda: StudentFactory().user,
        lambda: TeacherFactory().user,
        lambda: ExternalReviewerFactory().user,
    ],
    ids=["aluno", "professor", "avaliador_externo"],
)
def test_atualizacao_recusa_outros_perfis(db, edicao, make_user):
    client = APIClient()
    client.force_authenticate(make_user())

    resposta = patch(client, edicao, {"name": "Não deve gravar"})

    assert resposta.status_code == 403
    assert estado(edicao)[0] == "Desafio X 2030/1"


def test_atualizacao_sem_login_e_recusada(anonymous_client, edicao):
    # Divergência registrada: o OpenAPI declara 401/Bearer JWT; a aplicação
    resposta = patch(anonymous_client, edicao, {"name": "Não deve gravar"})

    assert resposta.status_code == 401
    assert resposta.data["error"]["code"] == "not_authenticated"
    assert estado(edicao)[0] == "Desafio X 2030/1"


def test_atualizacao_de_edicao_inexistente_devolve_404(client):
    resposta = client.patch(f"{LIST_URL}/999999", {"name": "x"}, format="json")

    assert resposta.status_code == 404
    assert resposta.data["error"]["code"] == "not_found"


def test_atualizacao_so_aceita_patch_e_nao_put(client, edicao):
    resposta = client.put(detail_url(edicao), {"name": "x"}, format="json")

    assert resposta.status_code == 405
    assert estado(edicao)[0] == "Desafio X 2030/1"
