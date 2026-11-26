from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import (
    EditionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)

pytestmark = pytest.mark.django_db


def collection(edition):
    return f"/api/admin/editions/{edition.pk}/stages"


def detail(stage):
    return f"/api/admin/stages/{stage.pk}"


@pytest.fixture
def admin_client():
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.ADMIN))
    return client


@pytest.fixture
def payload():
    start = timezone.now()
    return {
        "order": 1,
        "name": "Ideia",
        "kind": "SUBMISSION",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(days=1)).isoformat(),
        "evaluation_ends_at": (start + timedelta(days=2)).isoformat(),
        "max_score": "3.00",
        "submission_fields": [{"kind": "LINK"}],
    }


def test_quatro_operacoes_de_etapa_seguem_contrato(admin_client, payload):
    edition = EditionFactory()
    response = admin_client.get(collection(edition))
    assert (response.status_code, response.json()) == (200, [])
    response = admin_client.post(collection(edition), payload, format="json")
    assert response.status_code == 201
    data = response.json()
    assert mismatches(data, schema("Stage")) == []
    assert type(data["id"]) is int
    assert type(data["edition_id"]) is int and data["edition_id"] == edition.pk
    assert type(data["order"]) is int and data["order"] == 1
    assert data["scored"] is True
    assert type(data["min_evaluations"]) is int and data["min_evaluations"] == 1
    assert data["max_score"] == "3.00"
    for key in (
        "starts_at",
        "ends_at",
        "evaluation_ends_at",
        "created_at",
        "updated_at",
    ):
        assert parse_datetime(data[key]).utcoffset() is not None
    [field] = data["submission_fields"]
    assert mismatches(field, schema("DeliverableField")) == []
    assert type(field["id"]) is int
    assert (
        field["label"],
        field["required"],
        field["formats"],
        field["max_size_mb"],
    ) == ("", True, None, None)
    stage = edition.stages.get()
    response = admin_client.get(detail(stage))
    assert (response.status_code, response.json()) == (200, data)
    response = admin_client.patch(
        detail(stage),
        {"scored": False, "max_score": None, "submission_fields": []},
        format="json",
    )
    assert response.status_code == 200
    changed = response.json()
    assert mismatches(changed, schema("Stage")) == []
    assert changed["max_score"] is None and changed["submission_fields"] == []
    assert changed["evaluation_ends_at"] == data["evaluation_ends_at"]
    response = admin_client.get(collection(edition))
    assert (response.status_code, response.json()) == (200, [changed])


@pytest.mark.parametrize("status", [EditionStatus.PUBLISHED, EditionStatus.CLOSED])
def test_leitura_funciona_nos_estados_congelados(admin_client, status, payload):
    stage = StageFactory(edition__status=status, order=2)
    earlier = StageFactory(edition=stage.edition, order=1)
    StageFactory()
    assert admin_client.get(detail(stage)).status_code == 200
    response = admin_client.get(collection(stage.edition))
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [earlier.pk, stage.pk]
    code = (
        "edition_published" if status == EditionStatus.PUBLISHED else "edition_closed"
    )
    for response in (
        admin_client.post(collection(stage.edition), payload, format="json"),
        admin_client.patch(detail(stage), {"name": "Novo"}, format="json"),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == code


@pytest.mark.parametrize("operation", ["list", "create", "retrieve", "update"])
@pytest.mark.parametrize(
    "role", [None, UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_permissoes_da_api_de_etapas(operation, role):
    client = APIClient()
    if role is not None:
        client.force_authenticate(UserFactory(role=role))
    stage = StageFactory()
    response = {
        "list": lambda: client.get(collection(stage.edition)),
        "create": lambda: client.post(collection(stage.edition), {}, format="json"),
        "retrieve": lambda: client.get(detail(stage)),
        "update": lambda: client.patch(detail(stage), {}, format="json"),
    }[operation]()
    assert response.status_code == (401 if role is None else 403)
    assert response.json()["error"]["code"] == (
        "not_authenticated" if role is None else "permission_denied"
    )


def test_rotas_retornam_not_found_antes_de_validar_corpo(admin_client):
    stage = StageFactory()
    detail_url = detail(stage)
    collection_url = collection(stage.edition)
    edition = stage.edition
    stage.delete()
    edition.delete()
    for response in (
        admin_client.get(collection_url),
        admin_client.get(detail_url),
        admin_client.post(collection_url, {}, format="json"),
        admin_client.patch(detail_url, {}, format="json"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {"edition_id": 1},
        {"name": None},
        {"order": "1"},
        {"order": True},
        {"order": 32768},
        {"min_evaluations": 32768},
        {"scored": "true"},
        {"max_score": 3},
        {"max_score": "3.000"},
        {"max_score": "1e0"},
        {"max_score": " 3"},
        {"starts_at": "2026-11-26T00:00:00"},
        {"ends_at": None},
        {"submission_fields": None},
        {"submission_fields": [{"id": 1}]},
        {"submission_fields": [{"kind": "FILE", "max_size_mb": 32768}]},
        {"submission_fields": [{"kind": "LINK", "formats": "pdf"}]},
        {"submission_fields": [{"kind": "LINK", "extra": True}]},
    ],
)
def test_patch_recusa_entrada_invalida_sem_alterar_etapa(admin_client, body):
    stage = StageFactory()
    field = StageSubmissionFieldFactory(stage=stage)
    response = admin_client.patch(detail(stage), body, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    previous = stage.updated_at
    stage.refresh_from_db()
    assert stage.updated_at == previous
    assert stage.submission_fields.get().pk == field.pk


def test_post_e_patch_traduzem_posicao_conflitante(admin_client, payload):
    stage = StageFactory(order=1, max_score=Decimal("1"))
    another = StageFactory(edition=stage.edition, order=2, max_score=Decimal("1"))
    for response in (
        admin_client.post(collection(stage.edition), payload, format="json"),
        admin_client.patch(detail(another), {"order": 1}, format="json"),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "stage_position_taken"
