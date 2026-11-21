import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    EmailDomainFactory,
    ExternalReviewerFactory,
    StudentFactory,
    TeacherFactory,
    UserFactory,
)
from apps.accounts.models import EmailDomain

pytestmark = pytest.mark.django_db

EMAIL_DOMAINS_URL = "/api/admin/email-domains"


@pytest.fixture
def admin_client():
    admin = UserFactory(role=UserRole.ADMIN)
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


def test_usuario_nao_autenticado_nao_acessa_dominios():
    client = APIClient()

    assert client.get(EMAIL_DOMAINS_URL).status_code == 403
    assert (
        client.post(
            EMAIL_DOMAINS_URL,
            {"name": "teste.edu.br", "role": UserRole.STUDENT},
            format="json",
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "factory", [StudentFactory, TeacherFactory, ExternalReviewerFactory]
)
def test_usuario_nao_admin_nao_acessa_dominios(factory):
    client = APIClient()
    client.force_authenticate(user=factory().user)

    assert client.get(EMAIL_DOMAINS_URL).status_code == 403
    assert (
        client.post(
            EMAIL_DOMAINS_URL,
            {"name": "teste.edu.br", "role": UserRole.STUDENT},
            format="json",
        ).status_code
        == 403
    )


def test_admin_lista_e_filtra_dominios(admin_client):
    d1 = EmailDomainFactory(name="b.edu.br", role=UserRole.STUDENT, active=True)
    d2 = EmailDomainFactory(name="a.edu.br", role=UserRole.TEACHER, active=False)

    resp = admin_client.get(EMAIL_DOMAINS_URL)
    assert resp.status_code == 200
    assert [item["id"] for item in resp.data] == [d2.id, d1.id]

    resp_active = admin_client.get(f"{EMAIL_DOMAINS_URL}?active=true")
    assert resp_active.status_code == 200
    assert [item["id"] for item in resp_active.data] == [d1.id]

    resp_role = admin_client.get(f"{EMAIL_DOMAINS_URL}?role={UserRole.TEACHER}")
    assert resp_role.status_code == 200
    assert [item["id"] for item in resp_role.data] == [d2.id]


def test_admin_cadastra_dominio(admin_client):
    resp = admin_client.post(
        EMAIL_DOMAINS_URL,
        {"name": " A.Catolica-TO.edu.br ", "role": UserRole.STUDENT},
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["name"] == "a.catolica-to.edu.br"
    assert resp.data["role"] == UserRole.STUDENT
    assert resp.data["active"] is True
    assert EmailDomain.objects.filter(name="a.catolica-to.edu.br").exists()


@pytest.mark.parametrize(
    "invalid_name",
    ["", "   ", "@aluno.edu.br", "localhost", "-a.edu.br", "a b.edu.br"],
)
def test_api_impede_cadastro_de_dominio_invalido(admin_client, invalid_name):
    resp = admin_client.post(
        EMAIL_DOMAINS_URL,
        {"name": invalid_name, "role": UserRole.STUDENT},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "validation_error"


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.EXTERNAL_REVIEWER, "OUTRO"])
def test_api_impede_perfil_invalido_no_cadastro(admin_client, role):
    resp = admin_client.post(
        EMAIL_DOMAINS_URL,
        {"name": "teste.edu.br", "role": role},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "validation_error"


def test_api_impede_cadastro_de_dominio_duplicado(admin_client):
    EmailDomainFactory(name="a.catolica-to.edu.br", role=UserRole.STUDENT)

    resp = admin_client.post(
        EMAIL_DOMAINS_URL,
        {"name": " A.CATOLICA-TO.EDU.BR ", "role": UserRole.TEACHER},
        format="json",
    )

    assert resp.status_code == 409
    assert resp.data["error"]["code"] == "email_domain_taken"


def test_admin_edita_e_ativa_desativa_dominio(admin_client):
    domain = EmailDomainFactory(
        name="antigo.edu.br", role=UserRole.STUDENT, active=True
    )

    resp = admin_client.patch(
        f"{EMAIL_DOMAINS_URL}/{domain.id}",
        {"name": "Novo.EDU.BR", "role": UserRole.TEACHER, "active": False},
        format="json",
    )

    assert resp.status_code == 200
    assert resp.data == {
        "id": domain.id,
        "name": "novo.edu.br",
        "role": UserRole.TEACHER,
        "active": False,
    }

    resp_reactivate = admin_client.patch(
        f"{EMAIL_DOMAINS_URL}/{domain.id}",
        {"active": True},
        format="json",
    )
    assert resp_reactivate.status_code == 200
    assert resp_reactivate.data["active"] is True


def test_api_edicao_rejeita_payload_vazio_duplicado_e_inexistente(admin_client):
    EmailDomainFactory(name="existente.edu.br", role=UserRole.STUDENT)
    domain = EmailDomainFactory(name="outro.edu.br", role=UserRole.TEACHER)

    empty = admin_client.patch(f"{EMAIL_DOMAINS_URL}/{domain.id}", {}, format="json")
    assert empty.status_code == 400
    assert empty.data["error"]["code"] == "validation_error"

    dup = admin_client.patch(
        f"{EMAIL_DOMAINS_URL}/{domain.id}",
        {"name": "EXISTENTE.edu.br"},
        format="json",
    )
    assert dup.status_code == 409
    assert dup.data["error"]["code"] == "email_domain_taken"

    missing = admin_client.patch(
        f"{EMAIL_DOMAINS_URL}/999999",
        {"active": False},
        format="json",
    )
    assert missing.status_code == 404
    assert missing.data["error"]["code"] == "email_domain_not_found"
