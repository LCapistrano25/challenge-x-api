import pytest
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import (
    CriterionFactory,
    EditionFactory,
    StageCriterionFactory,
)
from apps.editions.models import Criterion
from apps.evaluations.factories import EvaluationFactory

pytestmark = pytest.mark.django_db


def collection(edition):
    return f"/api/admin/editions/{edition.pk}/criteria"


def detail(criterion):
    return f"/api/admin/criteria/{criterion.pk}"


@pytest.fixture
def admin_client():
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.ADMIN))
    return client


def test_cria_e_lista_criterios_conforme_contrato(admin_client):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    CriterionFactory()
    path = collection(edition)
    assert admin_client.get(path).json() == []

    response = admin_client.post(
        path,
        {"name": "  Inovação  ", "rubric": "  texto  ", "tiebreak_order": 32767},
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert mismatches(data, schema("Criterion")) == []
    assert data["name"] == "Inovação"
    assert data["rubric"] == "  texto  "
    assert type(data["id"]) is int
    assert type(data["edition_id"]) is int and data["edition_id"] == edition.pk
    assert type(data["tiebreak_order"]) is int and data["tiebreak_order"] == 32767
    assert all(
        parse_datetime(data[field]).utcoffset() is not None
        for field in ("created_at", "updated_at")
    )
    assert admin_client.get(path).json() == [data]


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {"name": "x", "extra": 1},
        {"name": ""},
        {"name": "   "},
        {"name": None},
        {"name": True},
        {"name": 12},
        {"name": "x" * 151},
        {"name": "x", "rubric": 1},
        {"name": "x", "tiebreak_order": "1"},
        {"name": "x", "tiebreak_order": True},
        {"name": "x", "tiebreak_order": 1.5},
        {"name": "x", "tiebreak_order": 0},
        {"name": "x", "tiebreak_order": 32768},
    ],
)
def test_post_invalido_nao_persiste(admin_client, body):
    edition = EditionFactory()
    response = admin_client.post(collection(edition), body, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert not Criterion.objects.filter(edition=edition).exists()


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": "existente", "tiebreak_order": 1}, "criterion_name_taken"),
        ({"name": "Outro", "tiebreak_order": 1}, "tiebreak_order_taken"),
    ],
)
def test_post_conflitos_de_unicidade(admin_client, body, code):
    existing = CriterionFactory(name="Existente", tiebreak_order=1)
    response = admin_client.post(collection(existing.edition), body, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
    assert Criterion.objects.filter(edition=existing.edition).count() == 1


def test_edicao_encerrada_pode_listar_mas_nao_criar(admin_client):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    assert admin_client.get(collection(edition)).status_code == 200
    response = admin_client.post(collection(edition), {"name": "Novo"}, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "edition_closed"
    assert not Criterion.objects.filter(edition=edition).exists()


def test_patch_parcial_e_nulabilidade(admin_client):
    criterion = CriterionFactory(rubric="Faixas", tiebreak_order=1)
    response = admin_client.patch(detail(criterion), {"name": " Novo "}, format="json")
    assert response.status_code == 200
    assert mismatches(response.json(), schema("Criterion")) == []
    assert response.json()["name"] == "Novo"
    assert response.json()["rubric"] == "Faixas"
    assert response.json()["tiebreak_order"] == 1

    response = admin_client.patch(
        detail(criterion), {"rubric": None, "tiebreak_order": None}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["rubric"] is None
    assert response.json()["tiebreak_order"] is None
    criterion.refresh_from_db()
    assert criterion.rubric == ""
    assert criterion.tiebreak_order is None


@pytest.mark.parametrize(
    "body", [{}, [], {"edition_id": 1}, {"name": None}, {"tiebreak_order": 32768}]
)
def test_patch_invalido_nao_altera_criterio(admin_client, body):
    criterion = CriterionFactory()
    before = Criterion.objects.values().get(pk=criterion.pk)
    response = admin_client.patch(detail(criterion), body, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert Criterion.objects.values().get(pk=criterion.pk) == before


def test_patch_bloqueia_apenas_avaliacao_em_etapa_vinculada(admin_client):
    criterion = CriterionFactory()
    link = StageCriterionFactory(criterion=criterion, stage__edition=criterion.edition)
    EvaluationFactory(stage__edition=criterion.edition)
    response = admin_client.patch(detail(criterion), {"name": "Novo"}, format="json")
    assert response.status_code == 200

    EvaluationFactory(stage=link.stage)
    response = admin_client.patch(
        detail(criterion), {"name": "Bloqueado"}, format="json"
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "criterion_in_use_by_evaluations"
    criterion.refresh_from_db()
    assert criterion.name == "Novo"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": "existente", "tiebreak_order": 1}, "criterion_name_taken"),
        ({"tiebreak_order": 1}, "tiebreak_order_taken"),
    ],
)
def test_patch_conflitos_de_unicidade(admin_client, body, code):
    existing = CriterionFactory(name="Existente", tiebreak_order=1)
    criterion = CriterionFactory(edition=existing.edition, name="Original")
    response = admin_client.patch(detail(criterion), body, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
    criterion.refresh_from_db()
    assert criterion.name == "Original"
    assert criterion.tiebreak_order is None


def test_patch_edicao_encerrada_tem_precedencia_sobre_avaliacao(admin_client):
    criterion = CriterionFactory(edition__status=EditionStatus.CLOSED)
    link = StageCriterionFactory(criterion=criterion, stage__edition=criterion.edition)
    EvaluationFactory(stage=link.stage)
    response = admin_client.patch(detail(criterion), {"name": "Novo"}, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "edition_closed"


def test_delete_sem_vinculo_retorna_204(admin_client):
    criterion = CriterionFactory(edition__status=EditionStatus.PUBLISHED)
    response = admin_client.delete(detail(criterion))
    assert response.status_code == 204
    assert response.content == b""
    assert not Criterion.objects.filter(pk=criterion.pk).exists()


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (EditionStatus.SETUP, "criterion_linked_to_stage"),
        (EditionStatus.CLOSED, "edition_closed"),
    ],
)
def test_delete_recusa_criterio_vinculado_ou_edicao_encerrada(
    admin_client, status, code
):
    criterion = CriterionFactory(edition__status=status)
    StageCriterionFactory(criterion=criterion, stage__edition=criterion.edition)
    response = admin_client.delete(detail(criterion))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
    assert Criterion.objects.filter(pk=criterion.pk).exists()


@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
@pytest.mark.parametrize(
    "role", [None, UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_acesso_aos_criterios_restrito_a_admin(method, role):
    criterion = CriterionFactory()
    path = (
        collection(criterion.edition)
        if method in {"get", "post"}
        else detail(criterion)
    )
    client = APIClient()
    if role is not None:
        client.force_authenticate(UserFactory(role=role))
    response = getattr(client, method)(path)
    assert response.status_code == (401 if role is None else 403)
    assert response.json()["error"]["code"] == (
        "not_authenticated" if role is None else "permission_denied"
    )


@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
def test_criterio_ou_edicao_inexistente(admin_client, method):
    criterion = CriterionFactory()
    edition = criterion.edition
    path = collection(edition) if method in {"get", "post"} else detail(criterion)
    criterion.delete()
    edition.delete()
    response = getattr(admin_client, method)(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_patch_em_edicao_publicada(admin_client):
    criterion = CriterionFactory(edition__status=EditionStatus.PUBLISHED)
    response = admin_client.patch(
        detail(criterion), {"name": "Revisado"}, format="json"
    )
    assert response.status_code == 200
    criterion.refresh_from_db()
    assert criterion.name == "Revisado"


def test_patch_bloqueia_criterio_com_avaliacao_finalizada(admin_client):
    criterion = CriterionFactory()
    link = StageCriterionFactory(criterion=criterion, stage__edition=criterion.edition)
    EvaluationFactory(stage=link.stage, finalized=True)
    before = Criterion.objects.values().get(pk=criterion.pk)
    response = admin_client.patch(
        detail(criterion), {"name": "Revisado"}, format="json"
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "criterion_in_use_by_evaluations"
    assert Criterion.objects.values().get(pk=criterion.pk) == before
