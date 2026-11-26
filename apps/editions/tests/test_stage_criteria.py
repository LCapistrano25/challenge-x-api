"""UC08 — critérios e pontuações da etapa (RF08, D-02)."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed, EditionPublished
from apps.editions.factories import (
    CriterionFactory,
    EditionFactory,
    StageCriterionFactory,
    StageFactory,
)
from apps.editions.models import StageCriterion
from apps.editions.use_cases.configure_stage_criteria import configure_stage_criteria

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def stage():
    return StageFactory(edition=EditionFactory())


def item(criterion, score="10.00"):
    return {"criterion_id": criterion.pk, "max_score": Decimal(score)}


def scores(stage):
    return dict(
        StageCriterion.objects.filter(stage=stage).values_list(
            "criterion_id", "max_score"
        )
    )


# Caso de uso


def test_soma_dos_criterios_nao_precisa_igualar_a_etapa(admin, stage):
    # D-02: a etapa vale 3, e dois critérios de 10 são aceitos como pesos.
    a, b = (CriterionFactory(edition=stage.edition) for _ in range(2))

    result = configure_stage_criteria(
        actor=admin, stage=stage, items=[item(a), item(b)]
    )

    assert [link.criterion_id for link in result] == sorted([a.pk, b.pk])
    assert scores(stage) == {a.pk: Decimal("10.00"), b.pk: Decimal("10.00")}


def test_lista_substitui_o_conjunto_e_mantem_o_vinculo(admin, stage):
    kept = StageCriterionFactory(stage=stage)
    removed = StageCriterionFactory(stage=stage)
    new = CriterionFactory(edition=stage.edition)

    configure_stage_criteria(
        actor=admin, stage=stage, items=[item(kept.criterion, "5.00"), item(new)]
    )

    assert scores(stage) == {
        kept.criterion_id: Decimal("5.00"),
        new.pk: Decimal("10.00"),
    }
    assert StageCriterion.objects.filter(pk=kept.pk).exists()
    assert not StageCriterion.objects.filter(pk=removed.pk).exists()


def test_lista_vazia_desvincula_tudo(admin, stage):
    StageCriterionFactory(stage=stage)

    assert configure_stage_criteria(actor=admin, stage=stage, items=[]) == []
    assert scores(stage) == {}


@pytest.mark.parametrize("case", ["nao_pontuada", "repetido", "outra_edicao", "zero"])
def test_regras_barram_sem_mudar_nada(admin, stage, case):
    link = StageCriterionFactory(stage=stage)
    criterion = CriterionFactory(edition=stage.edition)
    items = [item(criterion)]
    if case == "nao_pontuada":
        stage = StageFactory(edition=stage.edition, scored=False, max_score=None)
    elif case == "repetido":
        items = [item(criterion), item(criterion, "5.00")]
    elif case == "outra_edicao":
        items = [item(CriterionFactory())]
    else:
        items = [item(criterion, "0.00")]

    with pytest.raises(ValidationError):
        configure_stage_criteria(actor=admin, stage=stage, items=items)
    assert scores(link.stage) == {link.criterion_id: link.max_score}


@pytest.mark.parametrize(
    "status, error",
    [
        (EditionStatus.PUBLISHED, EditionPublished),
        (EditionStatus.CLOSED, EditionClosed),
    ],
)
def test_edicao_publicada_ou_encerrada_nao_muda(admin, stage, status, error):
    criterion = CriterionFactory(edition=stage.edition)
    stage.edition.status = status
    stage.edition.save()

    with pytest.raises(error):
        configure_stage_criteria(actor=admin, stage=stage, items=[item(criterion)])
    assert scores(stage) == {}


def test_exige_admin(stage):
    criterion = CriterionFactory(edition=stage.edition)

    with pytest.raises(NotAdminActor):
        configure_stage_criteria(
            actor=UserFactory(role=UserRole.TEACHER),
            stage=stage,
            items=[item(criterion)],
        )


# API


def url(stage_id):
    return f"/api/admin/stages/{stage_id}/criteria"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_get_e_put_seguem_o_contrato(admin, stage):
    criterion = CriterionFactory(edition=stage.edition)
    client = client_for(admin)
    body = {"items": [{"criterion_id": criterion.pk, "max_score": "10.00"}]}
    assert mismatches(body, schema("StageCriteriaUpdate")) == []

    saved = client.put(url(stage.pk), body, format="json")
    listed = client.get(url(stage.pk))

    for response in (saved, listed):
        assert response.status_code == 200
        data = response.json()
        assert (
            mismatches(data, {"type": "array", "items": schema("StageCriterion")}) == []
        )
        assert data[0]["criterion"] == {"id": criterion.pk, "name": criterion.name}
        assert data[0]["max_score"] == "10.00"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"items": [{"criterion_id": 1}]},
        {"items": [{"criterion_id": 1, "max_score": 10}]},
        {"items": [{"criterion_id": 1, "max_score": "10.00", "extra": 1}]},
        {"items": [], "extra": 1},
    ],
)
def test_corpo_fora_do_contrato_responde_400(admin, stage, body):
    response = client_for(admin).put(url(stage.pk), body, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_regra_violada_responde_400(admin, stage):
    body = {"items": [{"criterion_id": CriterionFactory().pk, "max_score": "10.00"}]}

    response = client_for(admin).put(url(stage.pk), body, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_edicao_publicada_responde_409(admin, stage):
    stage.edition.status = EditionStatus.PUBLISHED
    stage.edition.save()

    response = client_for(admin).put(url(stage.pk), {"items": []}, format="json")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "edition_published"


@pytest.mark.parametrize("method", ["get", "put"])
def test_etapa_inexistente_responde_404(admin, method):
    response = getattr(client_for(admin), method)(
        url(999999), {"items": []}, format="json"
    )

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["get", "put"])
def test_sem_login_401_e_papel_errado_403(stage, method):
    anonymous = getattr(APIClient(), method)(
        url(stage.pk), {"items": []}, format="json"
    )
    teacher = getattr(client_for(UserFactory(role=UserRole.TEACHER)), method)(
        url(stage.pk), {"items": []}, format="json"
    )

    assert anonymous.status_code == 401
    assert teacher.status_code == 403
