"""Testes de contrato da #122 (UC18, UC19): o OpenAPI é a fonte de verdade.

Os quatro endpoints são comparados com `docs/api/openapi.yaml`, lido com PyYAML e
checado por um validador mínimo de JSON Schema (sem dependência nova). O teste
pergunta ao contrato; nunca copia o que a implementação faz.

Como ler uma falha:
- teste vermelho: incompatibilidade que a implementação pode corrigir sozinha;
- `xfail(strict=True)` com motivo: incompatibilidade que depende de decisão da
  equipe, de Models/banco ou de código transversal. Se passar, o strict avisa.

Exemplos do contrato só viram exigência quando têm função de contrato: os códigos
de erro dos exemplos (400, 403, 404 e as chaves de 409) são o catálogo estável de
códigos (P-37); valores como `details.title` ou nomes de edição são ilustrativos.
"""

import json
import re
from datetime import datetime
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.editions.models import Category, Criterion, Edition

SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.yaml"
LIST_URL = "/api/admin/editions"
LIST_PATH = "/api/admin/editions"
DETAIL_PATH = "/api/admin/editions/{edition_id}"
OPERATIONS = [
    ("get", LIST_PATH),
    ("post", LIST_PATH),
    ("get", DETAIL_PATH),
    ("patch", DETAIL_PATH),
]
PASSWORD = "TesteForte!2026x"
DROP = ...  # em um caso de payload, remove o campo


# ------------------------------------------------------------ leitura do contrato


@cache
def spec():
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def deref(node):
    while isinstance(node, dict) and "$ref" in node:
        target = spec()
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def operation(method, path):
    return spec()["paths"][path][method]


def documented_responses(method, path):
    responses = operation(method, path)["responses"]
    return {int(code): deref(response) for code, response in responses.items()}


def json_schema_of(response):
    content = response.get("content", {}).get("application/json")
    return content["schema"] if content else None


def request_schema(method, path):
    body = deref(operation(method, path)["requestBody"])
    return body["content"]["application/json"]["schema"]


def documented_codes(method, path, status):
    """Códigos de erro que o contrato lista para o status (exemplos da resposta)."""
    content = documented_responses(method, path)[status]["content"]["application/json"]
    examples = content.get("examples") or {"unico": {"value": content["example"]}}
    return {e["value"]["error"]["code"] for e in examples.values()}


# ------------------------------------------------- validador mínimo de JSON Schema

SUPPORTED = {
    "$ref", "type", "enum", "minimum", "maximum", "minLength", "maxLength", "format",
    "properties", "required", "additionalProperties", "minProperties", "items",
    "description", "examples", "example",
}  # fmt: skip
DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)


def has_type(value, name):
    if name == "null":
        return value is None
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":  # 5.0 é inteiro no JSON Schema; True não é
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (
            isinstance(value, float) and value.is_integer()
        )
    if name == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    raise AssertionError(f"tipo sem suporte no validador: {name}")


def has_format(value, name):
    if name == "date-time":
        if not DATE_TIME.match(value):
            return False
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return True
    if name == "uri":
        parsed = urlparse(value)
        return bool(parsed.scheme and parsed.netloc)
    raise AssertionError(f"formato sem suporte no validador: {name}")


def validate(schema, value, path="$"):
    """Erros de `value` contra `schema`; lista vazia = válido.

    Segue o JSON Schema 2020-12 do OpenAPI 3.1: 5.0 é inteiro, True não é número,
    `enum` compara tipo e valor. Só `description`, `example` e `examples` são
    ignorados (ilustrativos, não restringem). `format` é checado como asserção,
    mais rígido que a especificação (anotação por padrão), e `uri` exige
    esquema e host, o que cobre as URLs http(s) do contrato.
    """
    schema = deref(schema)
    unsupported = set(schema) - SUPPORTED
    assert not unsupported, f"palavra-chave sem suporte no validador: {unsupported}"

    if "type" in schema:
        names = schema["type"]
        names = names if isinstance(names, list) else [names]
        if not any(has_type(value, n) for n in names):
            return [f"{path}: {type(value).__name__} não é {names}"]
    errors = []
    if "enum" in schema and not any(
        isinstance(value, bool) == isinstance(e, bool) and value == e
        for e in schema["enum"]
    ):
        errors.append(f"{path}: {value!r} fora de {schema['enum']}")
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > {schema['maximum']}")
    if isinstance(value, str):
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: {len(value)} caracteres > {schema['maxLength']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: menos que {schema['minLength']} caracteres")
        if "format" in schema and not has_format(value, schema["format"]):
            errors.append(f"{path}: {value!r} não é {schema['format']}")
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: falta {name}")
        props = schema.get("properties", {})
        assert schema.get("additionalProperties", True) in (True, False), (
            "additionalProperties com schema não é suportado pelo validador"
        )
        if schema.get("additionalProperties") is False:
            errors += [
                f"{path}: campo extra {n}" for n in sorted(set(value) - set(props))
            ]
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: menos de {schema['minProperties']} campos")
        for name, sub in props.items():
            if name in value:
                errors += validate(sub, value[name], f"{path}.{name}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors += validate(schema["items"], item, f"{path}[{i}]")
    return errors


# ---------------------------------------------------------------------- auxiliares


def admin_client():
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.ADMIN))
    return client


def send(client, method, url, payload=None, *, raw=False):
    """Envia `payload` como JSON cru (aceita null, lista, texto), sem o `format`."""
    if payload is None and not raw:
        return getattr(client, method)(url)
    return client.generic(
        method.upper(), url, json.dumps(payload), content_type="application/json"
    )


def body_of(resposta):
    return json.loads(resposta.content)


def error_code(resposta):
    return body_of(resposta)["error"]["code"]


def assert_matches_contract(resposta, method, path):
    """Status documentado, JSON e corpo válido contra o schema daquele status."""
    documented = documented_responses(method, path)
    assert resposta.status_code in documented, (
        f"{resposta.status_code} não está documentado em {method.upper()} {path}: "
        f"{sorted(documented)}"
    )
    assert resposta["Content-Type"].startswith("application/json"), resposta[
        "Content-Type"
    ]
    schema = json_schema_of(documented[resposta.status_code])
    if schema is not None:
        errors = validate(schema, body_of(resposta))
        assert not errors, errors


def state(edition):
    edition.refresh_from_db()
    return edition.name, edition.min_members, edition.max_members, edition.status


def make_edition(status=EditionStatus.SETUP, **extra):
    return EditionFactory(name="Base", status=status, **extra)


def detail_url(edition):
    return f"{LIST_URL}/{edition.pk}"


def fully_filled_edition():
    return EditionFactory(
        name="Completa",
        status=EditionStatus.CLOSED,
        regulation_url="https://storage.exemplo.edu.br/editais/2026-1.pdf",
        published_at=timezone.now(),
        closed_at=timezone.now(),
    )


# ------------------------------------------------------------- rotas e métodos


@pytest.mark.parametrize(("method", "path"), OPERATIONS)
def test_rota_do_contrato_existe_e_a_view_trata_o_metodo(db, method, path):
    url = path.replace("{edition_id}", "1")

    match = resolve(url)

    assert hasattr(match.func.cls, method)


@pytest.mark.parametrize("path", [LIST_PATH, DETAIL_PATH])
def test_view_so_trata_os_metodos_que_o_contrato_documenta(path):
    documented = {
        m
        for m in spec()["paths"][path]
        if m in {"get", "post", "put", "patch", "delete"}
    }
    view = resolve(path.replace("{edition_id}", "1")).func.cls

    implemented = {
        m for m in ("get", "post", "put", "patch", "delete") if hasattr(view, m)
    }

    assert implemented == documented


@pytest.mark.parametrize(
    ("method", "url"),
    [("put", LIST_URL), ("delete", LIST_URL), ("post", f"{LIST_URL}/1"),
     ("put", f"{LIST_URL}/1"), ("delete", f"{LIST_URL}/1")],
)  # fmt: skip
def test_metodo_fora_do_contrato_e_recusado(db, method, url):
    resposta = send(admin_client(), method, url, {})

    assert resposta.status_code == 405


def test_id_que_nao_e_inteiro_responde_erro_documentado_em_json(db):
    # O contrato não diz qual erro o id inválido gera (400 ou 404, ambos
    # documentados); exige só que seja um dos documentados, no formato Error.
    resposta = admin_client().get(f"{LIST_URL}/abc")

    assert_matches_contract(resposta, "get", DETAIL_PATH)


# ------------------------------------------------------------ schemas de saída


def test_lista_valida_contra_o_schema_com_todos_os_status(db):
    make_edition(EditionStatus.SETUP)
    make_edition(EditionStatus.PUBLISHED, published_at=timezone.now())
    fully_filled_edition()

    resposta = admin_client().get(LIST_URL)

    assert resposta.status_code == 200
    assert_matches_contract(resposta, "get", LIST_PATH)
    assert len(body_of(resposta)) == 3


@pytest.mark.parametrize(
    "build",
    [make_edition, fully_filled_edition, lambda: EditionFactory(name="")],
    ids=["basica", "completa", "sem_nome"],
)
def test_consulta_valida_contra_o_schema(db, build):
    edition = build()

    resposta = admin_client().get(detail_url(edition))

    assert resposta.status_code == 200
    assert_matches_contract(resposta, "get", DETAIL_PATH)


def test_resposta_traz_exatamente_as_propriedades_do_schema(db):
    edition = fully_filled_edition()
    properties = set(deref(spec()["components"]["schemas"]["Edition"])["properties"])

    resposta = admin_client().get(detail_url(edition))

    assert set(body_of(resposta)) == properties


def test_campos_nulos_do_schema_saem_como_null(db):
    edition = EditionFactory(name="", regulation_url="")

    corpo = body_of(admin_client().get(detail_url(edition)))

    assert corpo["name"] is None
    assert corpo["regulation_url"] is None
    assert corpo["published_at"] is None
    assert corpo["closed_at"] is None


def test_todo_status_do_contrato_e_alcancavel():
    contrato = set(spec()["components"]["schemas"]["EditionStatus"]["enum"])

    assert contrato == {s.value for s in EditionStatus}


# ----------------------------------------------------- schemas de entrada (POST)

NAME_101_WITH_SPACE = " " + "x" * 100  # 101 caracteres no contrato, 100 depois do trim

CREATE_CASES = [
    pytest.param({}, id="valido"),
    pytest.param({"name": DROP}, id="sem_nome"),
    pytest.param({"name": None}, id="nome_null"),
    pytest.param({"name": ""}, id="nome_vazio"),
    pytest.param({"name": "x" * 100}, id="nome_100"),
    pytest.param({"semester": 2}, id="semestre_2"),
    pytest.param({"year": 2101.0}, id="ano_com_ponto_zero"),
    pytest.param({"year": "2101"}, id="ano_texto"),
    pytest.param({"year": 2101.5}, id="ano_fracionario"),
    pytest.param({"year": True}, id="ano_booleano"),
    pytest.param({"year": None}, id="ano_null"),
    pytest.param({"year": DROP}, id="sem_ano"),
    pytest.param({"semester": 0}, id="semestre_0"),
    pytest.param({"semester": 3}, id="semestre_3"),
    pytest.param({"semester": "1"}, id="semestre_texto"),
    pytest.param({"semester": True}, id="semestre_booleano"),
    pytest.param({"semester": None}, id="semestre_null"),
    pytest.param({"semester": DROP}, id="sem_semestre"),
    pytest.param({"name": "x" * 101}, id="nome_101"),
    pytest.param({"name": NAME_101_WITH_SPACE}, id="nome_101_com_espaco"),
    pytest.param({"name": 5}, id="nome_numero"),
    pytest.param({"name": []}, id="nome_lista"),
    pytest.param({"status": "PUBLISHED"}, id="campo_status"),
    pytest.param({"min_members": 3}, id="campo_limites"),
    pytest.param(
        {"regulation_url": "https://x.edu.br/a.pdf"}, id="campo_regulation_url"
    ),
    pytest.param({"qualquer": 1}, id="campo_desconhecido"),
    pytest.param({"year": -1}, id="ano_negativo"),
    pytest.param({"year": 0}, id="ano_zero"),
    pytest.param({"year": 32768}, id="ano_acima_de_smallint"),
    pytest.param({"year": -(2**31)}, id="ano_minimo_int32"),
    pytest.param({"year": 2**31 - 1}, id="ano_maximo_int32"),
]


def apply(base, overrides):
    payload = {**base, **overrides}
    return {k: v for k, v in payload.items() if v is not DROP}


@pytest.mark.parametrize("overrides", CREATE_CASES)
def test_cadastro_aceita_exatamente_o_que_o_schema_aceita(db, overrides):
    payload = apply({"year": 2101, "semester": 1}, overrides)
    errors = validate(request_schema("post", LIST_PATH), payload)

    resposta = send(admin_client(), "post", LIST_URL, payload, raw=True)

    assert_matches_contract(resposta, "post", LIST_PATH)
    if errors:
        assert resposta.status_code == 400, f"o schema recusa: {errors}"
        assert error_code(resposta) == "validation_error"
        assert not Edition.objects.exists()
    else:
        assert resposta.status_code == 201, body_of(resposta)
        data = body_of(resposta)
        year = Edition.objects.get(pk=data["id"]).year
        assert data["year"] == year == payload["year"]


@pytest.mark.parametrize(
    "payload", [[], "texto", 1, None], ids=["lista", "texto", "numero", "null"]
)
def test_cadastro_recusa_corpo_que_nao_e_objeto(db, payload):
    assert validate(request_schema("post", LIST_PATH), payload)

    resposta = send(admin_client(), "post", LIST_URL, payload, raw=True)

    assert resposta.status_code == 400
    assert not Edition.objects.exists()


# --------------------------------------------------- schemas de entrada (PATCH)

PATCH_CASES = [
    pytest.param({"name": "Novo"}, id="nome"),
    pytest.param({"name": None}, id="nome_null"),
    pytest.param({"name": ""}, id="nome_vazio"),
    pytest.param({"name": "x" * 100}, id="nome_100"),
    pytest.param({"min_members": 1}, id="min_1"),
    pytest.param({"min_members": 4.0}, id="min_com_ponto_zero"),
    pytest.param({"max_members": 3}, id="max_3"),
    pytest.param({"max_members": 6.0}, id="max_com_ponto_zero"),
    pytest.param({"name": "Novo", "min_members": 2, "max_members": 6}, id="tudo"),
    pytest.param({"name": "x" * 101}, id="nome_101"),
    pytest.param({"name": NAME_101_WITH_SPACE}, id="nome_101_com_espaco"),
    pytest.param({"name": 5}, id="nome_numero"),
    pytest.param({"name": []}, id="nome_lista"),
    pytest.param({"min_members": "4"}, id="min_texto"),
    pytest.param({"min_members": 4.5}, id="min_fracionario"),
    pytest.param({"min_members": True}, id="min_booleano"),
    pytest.param({"min_members": None}, id="min_null"),
    pytest.param({"min_members": 0}, id="min_0"),
    pytest.param({"min_members": -1}, id="min_negativo"),
    pytest.param({"min_members": []}, id="min_lista"),
    pytest.param({"max_members": "4"}, id="max_texto"),
    pytest.param({"max_members": 4.5}, id="max_fracionario"),
    pytest.param({"max_members": True}, id="max_booleano"),
    pytest.param({"max_members": None}, id="max_null"),
    pytest.param({"max_members": 0}, id="max_0"),
    pytest.param({"max_members": {}}, id="max_objeto"),
    pytest.param({}, id="vazio"),
    pytest.param({"year": 2031}, id="campo_year"),
    pytest.param({"semester": 2}, id="campo_semester"),
    pytest.param({"status": "PUBLISHED"}, id="campo_status"),
    pytest.param({"id": 99}, id="campo_id"),
    pytest.param(
        {"regulation_url": "https://x.edu.br/a.pdf"}, id="campo_regulation_url"
    ),
    pytest.param({"name": "Novo", "qualquer": 1}, id="nome_com_campo_desconhecido"),
    pytest.param([], id="corpo_lista"),
    pytest.param("texto", id="corpo_texto"),
    pytest.param(1, id="corpo_numero"),
    pytest.param(None, id="corpo_null"),
    pytest.param(
        {"min_members": 32768, "max_members": 2**31 - 1},
        id="limites_acima_de_smallint",
    ),
]


@pytest.mark.parametrize("payload", PATCH_CASES)
def test_atualizacao_aceita_exatamente_o_que_o_schema_aceita(db, payload):
    edition = make_edition()
    errors = validate(request_schema("patch", DETAIL_PATH), payload)

    resposta = send(admin_client(), "patch", detail_url(edition), payload, raw=True)

    assert_matches_contract(resposta, "patch", DETAIL_PATH)
    if errors:
        assert resposta.status_code == 400, f"o schema recusa: {errors}"
        assert error_code(resposta) == "validation_error"
        assert state(edition) == ("Base", 3, 5, EditionStatus.SETUP)
    else:
        assert resposta.status_code == 200, body_of(resposta)
        edition.refresh_from_db()
        data = body_of(resposta)
        for field in ("min_members", "max_members"):
            if field in payload:
                assert data[field] == getattr(edition, field) == payload[field]


@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("media", ["multipart", "urlencoded"])
def test_so_aceita_o_formato_json_do_contrato(db, method, media):
    # O contrato só declara application/json. O status de recusa não é fixado
    # (400 é o documentado; 415 é o do HTTP): o que não pode é gravar o dado.
    edition = make_edition()
    url = LIST_URL if method == "post" else detail_url(edition)
    data = {"year": 2101, "semester": 1} if method == "post" else {"name": "Via form"}
    kwargs = (
        {"format": "multipart"}
        if media == "multipart"
        else {"content_type": "application/x-www-form-urlencoded"}
    )
    if media == "urlencoded":
        data = "&".join(f"{k}={v}" for k, v in data.items())

    resposta = getattr(admin_client(), method)(url, data, **kwargs)

    assert resposta.status_code in (400, 415)
    assert state(edition)[0] == "Base"
    assert Edition.objects.count() == 1


@pytest.mark.parametrize(
    ("method", "path"), [("post", LIST_PATH), ("patch", DETAIL_PATH)]
)
def test_json_malformado_retorna_400_sem_gravar(db, method, path):
    edition = make_edition()
    before = state(edition)
    url = LIST_URL if method == "post" else detail_url(edition)

    resposta = admin_client().generic(
        method.upper(), url, "{x", content_type="application/json"
    )

    assert resposta.status_code == 400
    assert_matches_contract(resposta, method, path)
    assert error_code(resposta) == "validation_error"
    assert body_of(resposta)["error"]["details"] == {
        "non_field_errors": ["O corpo da requisição está malformado."]
    }
    assert Edition.objects.count() == 1
    assert state(edition) == before


# --------------------------------------------- status, códigos de erro e regras


def s_list_ok():
    make_edition()
    return "get", LIST_PATH, LIST_URL, None


def s_detail_ok():
    return "get", DETAIL_PATH, detail_url(make_edition()), None


def s_detail_404():
    return "get", DETAIL_PATH, f"{LIST_URL}/999999", None


def s_post_created():
    return "post", LIST_PATH, LIST_URL, {"year": 2101, "semester": 1}


def s_post_invalid():
    return "post", LIST_PATH, LIST_URL, {"semester": 1}


def s_post_duplicate():
    EditionFactory(year=2101, semester=1)
    return "post", LIST_PATH, LIST_URL, {"year": 2101, "semester": 1}


def patch_of(edition, payload):
    return "patch", DETAIL_PATH, detail_url(edition), payload


def s_patch_setup():
    return patch_of(
        make_edition(), {"name": "Novo", "min_members": 2, "max_members": 6}
    )


def s_patch_published_name():
    return patch_of(make_edition(EditionStatus.PUBLISHED), {"name": "Novo"})


def s_patch_empty():
    return patch_of(make_edition(), {})


def s_patch_min_greater_than_max():
    return patch_of(make_edition(), {"min_members": 6, "max_members": 5})


def s_patch_min_above_current_max():
    return patch_of(make_edition(), {"min_members": 6})


def s_patch_404():
    return "patch", DETAIL_PATH, f"{LIST_URL}/999999", {"name": "x"}


def s_patch_published_limits():
    return patch_of(make_edition(EditionStatus.PUBLISHED), {"min_members": 2})


def s_patch_published_same_limits():
    return patch_of(
        make_edition(EditionStatus.PUBLISHED), {"min_members": 3, "max_members": 5}
    )


def s_patch_closed_name():
    return patch_of(make_edition(EditionStatus.CLOSED), {"name": "Novo"})


def s_patch_closed_limits():
    return patch_of(make_edition(EditionStatus.CLOSED), {"max_members": 6})


SCENARIOS = [
    (s_list_ok, 200, None),
    (s_detail_ok, 200, None),
    (s_detail_404, 404, "not_found"),
    (s_post_created, 201, None),
    (s_post_invalid, 400, "validation_error"),
    (s_post_duplicate, 409, "edition_exists"),
    (s_patch_setup, 200, None),
    (s_patch_published_name, 200, None),
    (s_patch_empty, 400, "validation_error"),
    (s_patch_404, 404, "not_found"),
    (s_patch_closed_name, 409, "edition_closed"),
    (s_patch_closed_limits, 409, "edition_closed"),
    # Incompatibilidades que a implementação pode corrigir (D-09 e D-10):
    (s_patch_min_greater_than_max, 400, "validation_error"),
    (s_patch_min_above_current_max, 400, "validation_error"),
    (s_patch_published_limits, 409, "edition_published"),
    (s_patch_published_same_limits, 409, "edition_published"),
]


@pytest.mark.parametrize(
    ("build", "status", "code"), SCENARIOS, ids=[c[0].__name__ for c in SCENARIOS]
)
def test_cenario_cumpre_o_contrato(db, build, status, code):
    method, path, url, payload = build()

    resposta = send(admin_client(), method, url, payload)

    assert resposta.status_code == status, body_of(resposta)
    assert_matches_contract(resposta, method, path)
    if code:
        assert error_code(resposta) == code


@pytest.mark.parametrize(("method", "path"), OPERATIONS)
def test_toda_operacao_documenta_o_que_a_implementacao_pode_devolver(method, path):
    documented = set(documented_responses(method, path))

    assert {401, 403} <= documented
    if path == DETAIL_PATH:
        assert 404 in documented
    if method in ("post", "patch"):
        assert {400, 409} <= documented


def test_codigos_de_conflito_do_contrato_sao_os_cobertos_pelos_cenarios():
    assert documented_codes("post", LIST_PATH, 409) == {"edition_exists"}
    assert documented_codes("patch", DETAIL_PATH, 409) == {
        "edition_published",
        "edition_closed",
    }


# ------------------------------------------------- persistência e regras do POST


def test_cadastro_persiste_em_configuracao_com_limites_3_a_5(db):
    resposta = send(
        admin_client(), "post", LIST_URL, {"year": 2101, "semester": 1}, raw=True
    )

    corpo = body_of(resposta)
    edition = Edition.objects.get(pk=corpo["id"])
    assert (corpo["status"], corpo["min_members"], corpo["max_members"]) == (
        "SETUP",
        3,
        5,
    )
    assert (edition.year, edition.semester) == (2101, 1)
    assert (corpo["published_at"], corpo["closed_at"], corpo["regulation_url"]) == (
        None,
        None,
        None,
    )


def test_cadastro_e_consulta_devolvem_a_mesma_edicao(db):
    client = admin_client()
    criada = body_of(
        send(
            client,
            "post",
            LIST_URL,
            {"year": 2101, "semester": 2, "name": "A"},
            raw=True,
        )
    )

    consultada = body_of(client.get(f"{LIST_URL}/{criada['id']}"))

    assert consultada == criada
    assert any(e == criada for e in body_of(client.get(LIST_URL)))


def test_atualizacao_persiste_e_a_consulta_reflete(db):
    client = admin_client()
    edition = make_edition()

    atualizada = body_of(
        send(
            client,
            "patch",
            detail_url(edition),
            {"name": "Novo", "min_members": 2},
            raw=True,
        )
    )

    assert state(edition) == ("Novo", 2, 5, EditionStatus.SETUP)
    assert body_of(client.get(detail_url(edition))) == atualizada


@pytest.mark.parametrize(
    "payload",
    [{"min_members": 2}, {"max_members": 6}, {"min_members": 6, "max_members": 5}],
    ids=["min", "max", "min_maior_que_max"],
)
def test_atualizacao_recusada_nao_grava_nem_o_nome(db, payload):
    edition = make_edition(EditionStatus.PUBLISHED)

    send(
        admin_client(),
        "patch",
        detail_url(edition),
        {"name": "Não grava", **payload},
        raw=True,
    )

    assert state(edition) == ("Base", 3, 5, EditionStatus.PUBLISHED)


@pytest.mark.xfail(
    strict=True,
    reason="P-18: o contrato manda pré-carregar categorias (Art. 2) e critérios "
    "(Quadro 1). Fora da issue #122 (RF47/RF48) e sem o conteúdo aprovado; "
    "depende da decisão da equipe.",
)
def test_cadastro_pre_carrega_categorias_e_criterios_padrao(db):
    resposta = send(
        admin_client(), "post", LIST_URL, {"year": 2101, "semester": 1}, raw=True
    )

    edition = Edition.objects.get(pk=body_of(resposta)["id"])
    assert Category.objects.filter(edition=edition).count() == 2
    assert Criterion.objects.filter(edition=edition).count() == 7


# ----------------------------------------------------------------- autorização


@pytest.mark.parametrize(
    "role", [UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
@pytest.mark.parametrize(("method", "path"), OPERATIONS)
def test_so_o_administrador_acessa(db, method, path, role):
    edition = make_edition()
    client = APIClient()
    client.force_authenticate(UserFactory(role=role))
    url = LIST_URL if path == LIST_PATH else detail_url(edition)
    payload = {
        "get": None,
        "post": {"year": 2101, "semester": 1},
        "patch": {"name": "x"},
    }[method]

    resposta = send(client, method, url, payload)

    assert resposta.status_code == 403
    assert_matches_contract(resposta, method, path)
    assert error_code(resposta) in documented_codes(method, path, 403)
    assert state(edition)[0] == "Base"
    assert Edition.objects.count() == 1


@pytest.mark.parametrize(("method", "path"), OPERATIONS)
def test_sem_autenticacao_responde_401_no_formato_do_contrato(db, method, path):
    edition = make_edition()
    url = LIST_URL if path == LIST_PATH else detail_url(edition)
    payload = {
        "get": None,
        "post": {"year": 2101, "semester": 1},
        "patch": {"name": "x"},
    }[method]

    resposta = send(APIClient(), method, url, payload)

    assert resposta.status_code == 401
    assert_matches_contract(resposta, method, path)
    assert error_code(resposta) in documented_codes(method, path, 401)
    assert state(edition)[0] == "Base"
    assert Edition.objects.count() == 1


# --------------------------------------------- sessão real e CSRF (rotas de sessão)


@pytest.fixture
def session_client(db):
    """Sessão real: login por senha e CSRF verificado, como no navegador."""
    UserFactory(email="admin.contrato@teste.com", role=UserRole.ADMIN)
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/auth/csrf").data["csrfToken"]
    resposta = client.post(
        "/api/auth/sessions/password",
        {"email": "admin.contrato@teste.com", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert resposta.status_code == 200, resposta.content
    client.csrf_token = client.get("/api/auth/csrf").data["csrfToken"]  # muda no login
    return client


def test_contrato_documenta_csrf_nas_rotas_de_sessao():
    login = operation("post", "/api/auth/sessions/password")["description"]

    assert "X-CSRFToken" in login


def test_sessao_real_consulta_sem_csrf(session_client):
    edition = make_edition()

    assert session_client.get(LIST_URL).status_code == 200
    assert session_client.get(detail_url(edition)).status_code == 200


def test_sessao_real_cadastra_com_csrf(session_client):
    resposta = session_client.post(
        LIST_URL,
        {"year": 2101, "semester": 1},
        format="json",
        HTTP_X_CSRFTOKEN=session_client.csrf_token,
    )

    assert resposta.status_code == 201
    assert_matches_contract(resposta, "post", LIST_PATH)


def test_sessao_real_atualiza_com_csrf(session_client):
    edition = make_edition()

    resposta = session_client.patch(
        detail_url(edition),
        {"name": "Via sessão"},
        format="json",
        HTTP_X_CSRFTOKEN=session_client.csrf_token,
    )

    assert resposta.status_code == 200
    assert state(edition)[0] == "Via sessão"


def test_sessao_real_sem_csrf_nao_cadastra(session_client):
    resposta = session_client.post(
        LIST_URL, {"year": 2101, "semester": 1}, format="json"
    )

    assert resposta.status_code == 403
    assert_matches_contract(resposta, "post", LIST_PATH)
    assert not Edition.objects.exists()


def test_sessao_real_sem_csrf_nao_atualiza(session_client):
    edition = make_edition()

    resposta = session_client.patch(
        detail_url(edition), {"name": "Sem token"}, format="json"
    )

    assert resposta.status_code == 403
    assert_matches_contract(resposta, "patch", DETAIL_PATH)
    assert state(edition)[0] == "Base"


def test_sessao_real_com_csrf_invalido_nao_atualiza(session_client):
    edition = make_edition()

    resposta = session_client.patch(
        detail_url(edition),
        {"name": "Token errado"},
        format="json",
        HTTP_X_CSRFTOKEN="invalido",
    )

    assert resposta.status_code == 403
    assert state(edition)[0] == "Base"
