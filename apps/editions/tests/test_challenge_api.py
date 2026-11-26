import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.factories import CourseFactory, SdgFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import ChallengeFactory, EditionFactory, EditionSdgFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.ADMIN))
    return client


@pytest.fixture
def challenge():
    return ChallengeFactory()


def collection(challenge):
    return f"/api/admin/editions/{challenge.edition_id}/challenges"


def detail(challenge):
    return f"/api/admin/challenges/{challenge.pk}"


def test_lista_com_filtros_e_shape_do_contrato(client, challenge):
    inactive = ChallengeFactory(
        edition=challenge.edition,
        course=challenge.course,
        sdg=challenge.sdg,
        active=False,
    )
    other_course = ChallengeFactory(edition=challenge.edition, sdg=challenge.sdg)
    other_number = 6 if challenge.sdg.number == 4 else 4
    other_sdg = ChallengeFactory(
        edition=challenge.edition,
        course=challenge.course,
        sdg=SdgFactory(number=other_number),
    )
    ChallengeFactory()
    response = client.get(
        collection(challenge),
        {
            "course_id": challenge.course_id,
            "sdg_id": challenge.sdg_id,
            "active": "true",
        },
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [challenge.pk]
    assert mismatches(response.json()[0], schema("Challenge")) == []
    assert {item["id"] for item in client.get(collection(challenge)).json()} == {
        challenge.pk,
        inactive.pk,
        other_course.pk,
        other_sdg.pk,
    }
    assert [
        item["id"]
        for item in client.get(collection(challenge), {"active": "false"}).json()
    ] == [inactive.pk]


def test_cadastra_e_responde_conforme_contrato(client, challenge):
    payload = {
        "course_id": challenge.course_id,
        "sdg_id": challenge.sdg_id,
        "description": "Descrição com ODS secundária no texto.",
    }
    response = client.post(collection(challenge), payload, format="json")
    assert response.status_code == 201
    body = response.json()
    assert mismatches(body, schema("Challenge")) == []
    assert body["active"] is True
    assert body["course"]["id"] == payload["course_id"]
    assert body["sdg"]["id"] == payload["sdg_id"]
    assert body["description"] == payload["description"]


def test_patch_parcial_preserva_campos_ausentes(client, challenge):
    response = client.patch(detail(challenge), {"active": False}, format="json")
    assert response.status_code == 200
    assert mismatches(response.json(), schema("Challenge")) == []
    description = challenge.description
    challenge.refresh_from_db()
    assert challenge.active is False
    assert challenge.description == description


def test_patch_pode_alterar_curso_e_ods(client, challenge):
    number = 6 if challenge.sdg.number == 4 else 4
    link = EditionSdgFactory(edition=challenge.edition, sdg=SdgFactory(number=number))
    course = CourseFactory()
    response = client.patch(
        detail(challenge),
        {"course_id": course.pk, "sdg_id": link.sdg_id},
        format="json",
    )
    assert response.status_code == 200
    challenge.refresh_from_db()
    assert challenge.course_id == course.pk
    assert challenge.sdg_id == link.sdg_id


def test_patch_invalido_nao_aplica_edicao_parcial(client, challenge):
    original = challenge.description
    response = client.patch(
        detail(challenge),
        {"course_id": CourseFactory(active=False).pk, "description": "Outro texto"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    challenge.refresh_from_db()
    assert challenge.description == original


@pytest.mark.parametrize("catalog", ["course", "sdg"])
@pytest.mark.parametrize("resend_id", [False, True], ids=["omitido", "reenviado"])
def test_patch_de_texto_preserva_vinculo_inativo(client, challenge, catalog, resend_id):
    linked = getattr(challenge, catalog)
    linked.active = False
    linked.save(update_fields=["active"])
    payload = {"description": "  Outro texto  "}
    if resend_id:
        payload[f"{catalog}_id"] = linked.pk
    response = client.patch(detail(challenge), payload, format="json")
    assert response.status_code == 200
    challenge.refresh_from_db()
    assert challenge.description == "Outro texto"
    assert getattr(challenge, f"{catalog}_id") == linked.pk


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_erro_de_ods_usa_sdg_id(client, challenge, active, method):
    # Uma ODS ativa mas não habilitada e uma inativa habilitada falham no mesmo campo.
    number = 6 if challenge.sdg.number == 4 else 4
    replacement = SdgFactory(number=number, active=active)
    if not active:
        EditionSdgFactory(edition=challenge.edition, sdg=replacement)
    original_description = challenge.description
    payload = {"sdg_id": replacement.pk, "description": "Outro texto"}
    if method == "post":
        payload["course_id"] = challenge.course_id
    path = collection(challenge) if method == "post" else detail(challenge)
    response = getattr(client, method)(path, payload, format="json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert set(error["details"]) == {"sdg_id"}
    challenge.refresh_from_db()
    assert challenge.sdg_id != replacement.pk
    assert challenge.description == original_description


@pytest.mark.parametrize("description", ["", "   "])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_descricao_em_branco_rejeitada(client, challenge, description, method):
    payload = {"description": description}
    if method == "post":
        payload.update(course_id=challenge.course_id, sdg_id=challenge.sdg_id)
    path = collection(challenge) if method == "post" else detail(challenge)
    response = getattr(client, method)(path, payload, format="json")
    assert response.status_code == 400
    assert "description" in response.json()["error"]["details"]


def test_admin_associa_erro_ao_campo_sdg(admin_client, challenge):
    number = 6 if challenge.sdg.number == 4 else 4
    unlinked = SdgFactory(number=number)
    response = admin_client.post(
        f"/admin/editions/challenge/{challenge.pk}/change/",
        {
            "edition": challenge.edition_id,
            "course": challenge.course_id,
            "sdg": unlinked.pk,
            "description": challenge.description,
            "active": "on",
        },
        HTTP_HOST="localhost",
    )
    assert response.status_code == 200
    assert "sdg" in response.context["adminform"].form.errors
    challenge.refresh_from_db()
    assert challenge.sdg_id != unlinked.pk


@pytest.mark.parametrize("payload", [{}, {"active": "false"}, {"edition_id": 2}])
def test_patch_rejeita_payload_fora_do_schema(client, challenge, payload):
    response = client.patch(detail(challenge), payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_escrita_em_edicao_encerrada(client, challenge):
    challenge.edition.status = EditionStatus.CLOSED
    challenge.edition.save(update_fields=["status"])
    payload = {
        "course_id": challenge.course_id,
        "sdg_id": challenge.sdg_id,
        "description": challenge.description,
    }
    for response in (
        client.post(collection(challenge), payload, format="json"),
        client.patch(detail(challenge), {"active": False}, format="json"),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "edition_closed"


@pytest.mark.parametrize("method", ["get", "post", "patch"])
@pytest.mark.parametrize(
    "role", [None, UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_acesso_restrito_ao_admin(challenge, method, role):
    client = APIClient()
    if role is not None:
        client.force_authenticate(UserFactory(role=role))
    path = detail(challenge) if method == "patch" else collection(challenge)
    assert getattr(client, method)(path).status_code == (401 if role is None else 403)


def test_patch_desafio_inexistente(client, challenge):
    path = detail(challenge)
    challenge.delete()
    response = client.patch(path, {"active": False}, format="json")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_listagem_edicao_inexistente(client):
    edition = EditionFactory()
    path = f"/api/admin/editions/{edition.pk}/challenges"
    edition.delete()
    assert client.get(path).status_code == 404
