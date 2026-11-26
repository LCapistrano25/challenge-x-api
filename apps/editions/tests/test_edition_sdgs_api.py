import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.core.factories import SdgFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import ChallengeFactory, EditionFactory, EditionSdgFactory
from apps.editions.use_cases.set_edition_sdgs import set_edition_sdgs

pytestmark = pytest.mark.django_db


@pytest.fixture
def edition():
    return EditionFactory()


@pytest.fixture
def admin_client():
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.ADMIN))
    return client


def url(edition):
    return f"/api/admin/editions/{edition.pk}/sdgs"


def enabled_ids(edition):
    return set(edition.sdg_links.values_list("sdg_id", flat=True))


def assert_sdg_response(response, *sdgs):
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert {item["id"] for item in body} == {sdg.pk for sdg in sdgs}
    assert all(mismatches(item, schema("Sdg")) == [] for item in body)


def test_lista_apenas_ods_da_edicao_incluindo_inativas(admin_client, edition):
    sdg = SdgFactory(number=4, active=False)
    EditionSdgFactory(edition=edition, sdg=sdg)
    EditionSdgFactory()

    response = admin_client.get(url(edition))
    assert_sdg_response(response, sdg)
    assert response.json()[0]["active"] is False


@pytest.mark.parametrize("with_challenge", [False, True])
def test_pode_manter_ods_inativa_ja_habilitada(admin_client, edition, with_challenge):
    inactive = SdgFactory(number=4, active=False)
    active = SdgFactory(number=6)
    link = EditionSdgFactory(edition=edition, sdg=inactive)
    if with_challenge:
        ChallengeFactory(edition=edition, sdg=inactive)

    response = admin_client.put(
        url(edition), {"sdg_ids": [inactive.pk, active.pk]}, format="json"
    )

    assert_sdg_response(response, inactive, active)
    assert enabled_ids(edition) == {inactive.pk, active.pk}
    link.refresh_from_db()


def test_rejeita_inclusao_inativa_sem_remover_vinculos(admin_client, edition):
    existing = EditionSdgFactory(edition=edition, sdg=SdgFactory(number=6)).sdg
    inactive = SdgFactory(number=4, active=False)

    response = admin_client.put(url(edition), {"sdg_ids": [inactive.pk]}, format="json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert enabled_ids(edition) == {existing.pk}


def test_pode_remover_ods_inativa_sem_desafio(admin_client, edition):
    EditionSdgFactory(edition=edition, sdg=SdgFactory(number=4, active=False))
    response = admin_client.put(url(edition), {"sdg_ids": []}, format="json")
    assert_sdg_response(response)
    assert not enabled_ids(edition)


def test_remocao_em_uso_rejeita_toda_a_substituicao(admin_client, edition):
    in_use = SdgFactory(number=4, active=False)
    other = SdgFactory(number=6)
    new = SdgFactory(number=7)
    ChallengeFactory(edition=edition, sdg=in_use)
    EditionSdgFactory(edition=edition, sdg=other)

    response = admin_client.put(url(edition), {"sdg_ids": [new.pk]}, format="json")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sdg_in_use"
    assert enabled_ids(edition) == {in_use.pk, other.pk}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"sdg_ids": [True]},
        {"sdg_ids": ["1"]},
        {"sdg_ids": [1, 1]},
        {"sdg_ids": [], "other": 1},
    ],
)
def test_rejeita_payload_fora_do_schema(admin_client, edition, payload):
    response = admin_client.put(url(edition), payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert not enabled_ids(edition)


def test_edicao_encerrada_recusa_escrita(admin_client):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    sdg = EditionSdgFactory(edition=edition).sdg
    response = admin_client.put(url(edition), {"sdg_ids": []}, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "edition_closed"
    assert enabled_ids(edition) == {sdg.pk}


@pytest.mark.parametrize("method", ["get", "put"])
def test_edicao_inexistente(admin_client, edition, method):
    path = url(edition)
    edition.delete()
    assert getattr(admin_client, method)(path).status_code == 404


@pytest.mark.parametrize("method", ["get", "put"])
@pytest.mark.parametrize(
    "role", [None, UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_acesso_restrito_ao_admin(edition, method, role):
    client = APIClient()
    if role is not None:
        client.force_authenticate(UserFactory(role=role))
    response = getattr(client, method)(url(edition))
    assert response.status_code == (401 if role is None else 403)


def test_caso_de_uso_rejeita_ator_nao_admin(edition):
    actor = UserFactory(role=UserRole.STUDENT)
    existing = EditionSdgFactory(edition=edition).sdg

    with pytest.raises(NotAdminActor):
        set_edition_sdgs(actor=actor, edition=edition, sdg_ids=[])

    assert enabled_ids(edition) == {existing.pk}
