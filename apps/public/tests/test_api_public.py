import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageFactory,
)
from apps.projects.factories import ProjectFactory
from apps.results.factories import ProjectResultFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def closed_edition():
    return EditionFactory(status=EditionStatus.CLOSED, closed_at=timezone.now())


def winner(edition, award=1, approved=True):
    project = ProjectFactory(
        team__edition=edition, category=CategoryFactory(edition=edition)
    )
    return ProjectResultFactory(
        project=project,
        award=award,
        approved_at=timezone.now() if approved else None,
    )


def test_edicao_vigente_segue_o_contrato(api_client):
    edition = EditionFactory(status=EditionStatus.PUBLISHED, name="Desafio X")
    StageFactory(edition=edition)
    challenge = ChallengeFactory(edition=edition)

    response = api_client.get("/api/public/editions/current")

    assert response.status_code == 200
    body = response.json()
    assert mismatches(body, schema("PublicEdition")) == []
    assert body["edition"]["id"] == edition.id
    assert [c["id"] for c in body["challenges"]] == [challenge.id]
    assert [s["id"] for s in body["sdgs"]] == [challenge.sdg_id]
    assert body["stages"][0]["phase_status"] == "OPEN"


def test_edicao_vigente_e_a_publicada(api_client):
    EditionFactory(status=EditionStatus.SETUP)
    closed_edition()
    publicada = EditionFactory(status=EditionStatus.PUBLISHED)

    response = api_client.get("/api/public/editions/current")

    assert response.json()["edition"]["id"] == publicada.id


def test_edicao_vigente_esconde_desafio_inativo(api_client):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    ChallengeFactory(edition=edition, active=False)

    response = api_client.get("/api/public/editions/current")

    assert response.json()["challenges"] == []


def test_sem_edicao_vigente_responde_404(api_client):
    EditionFactory(status=EditionStatus.SETUP)

    response = api_client.get("/api/public/editions/current")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_edicoes_encerradas_seguem_o_contrato(api_client):
    encerrada = closed_edition()
    EditionFactory(status=EditionStatus.PUBLISHED)

    response = api_client.get("/api/public/editions")

    assert response.status_code == 200
    body = response.json()
    assert [item["edition"]["id"] for item in body] == [encerrada.id]
    for item in body:
        assert mismatches(item, schema("PublicEditionListItem")) == []


def test_vencedores_seguem_o_contrato(api_client):
    edition = closed_edition()
    result = winner(edition)

    response = api_client.get(f"/api/public/editions/{edition.id}/winners")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert mismatches(body[0], schema("Winner")) == []
    assert body[0]["award"] == 1
    assert body[0]["project"]["id"] == result.project_id
    assert body[0]["project"]["members"]


def test_vencedores_so_com_resultado_homologado(api_client):
    edition = closed_edition()
    winner(edition, approved=False)

    response = api_client.get(f"/api/public/editions/{edition.id}/winners")

    assert response.json() == []


def test_vencedores_so_de_edicao_encerrada(api_client):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    winner(edition)

    response = api_client.get(f"/api/public/editions/{edition.id}/winners")

    assert response.json() == []


def test_vencedores_de_edicao_inexistente_responde_404(api_client):
    response = api_client.get("/api/public/editions/999999/winners")

    assert response.status_code == 404
