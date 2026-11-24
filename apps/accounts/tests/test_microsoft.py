import base64
import io
import json
from urllib.error import HTTPError

import pytest
from rest_framework.test import APIClient

from apps.accounts import microsoft
from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    DomainRoleMismatch,
    InactiveAccount,
    InvalidCredentials,
    MicrosoftIdentityMismatch,
)
from apps.accounts.factories import EmailDomainFactory, StudentFactory, UserFactory
from apps.accounts.microsoft import fetch_identity
from apps.accounts.models import User
from apps.accounts.rules import ensure_microsoft_domain
from apps.accounts.use_cases.authenticate_microsoft_user import (
    authenticate_microsoft_user,
)
from apps.core.exceptions import ExternalServiceError

# Login de aluno e professor com a conta Microsoft (RF18, RF36, RN02, P-42)

TENANT = "11111111-1111-1111-1111-111111111111"
CLIENT = "22222222-2222-2222-2222-222222222222"
OID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture(autouse=True)
def microsoft_settings(settings):
    settings.MICROSOFT_TENANT_ID = TENANT
    settings.MICROSOFT_CLIENT_ID = CLIENT
    settings.MICROSOFT_CLIENT_SECRET = "segredo"
    settings.MICROSOFT_REDIRECT_URI = "http://localhost/callback"


@pytest.fixture
def domains(db):
    EmailDomainFactory(name="a.edu.br", role=UserRole.STUDENT)
    EmailDomainFactory(name="p.edu.br", role=UserRole.TEACHER)
    EmailDomainFactory(name="admin.edu.br", role=UserRole.ADMIN)


def id_token(**claims):
    claims = {"tid": TENANT, "aud": CLIENT, "oid": OID, "name": "Ana", **claims}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"header.{payload.decode()}.assinatura"


def microsoft_returns(monkeypatch, **claims):
    claims.setdefault("preferred_username", "Ana@A.edu.br")
    body = json.dumps({"id_token": id_token(**claims)}).encode()
    monkeypatch.setattr(microsoft, "urlopen", lambda *a, **k: io.BytesIO(body))


def microsoft_fails(monkeypatch, error):
    def urlopen(*args, **kwargs):
        raise error

    monkeypatch.setattr(microsoft, "urlopen", urlopen)


def http_error(code, body):
    return HTTPError("url", code, "erro", {}, io.BytesIO(json.dumps(body).encode()))


# Troca do código (fetch_identity)


def test_devolve_a_identidade_com_o_email_em_minusculas(monkeypatch):
    microsoft_returns(monkeypatch)

    assert fetch_identity("codigo") == {
        "microsoft_id": OID,
        "email": "ana@a.edu.br",
        "name": "Ana",
    }


@pytest.mark.parametrize(
    "claims", [{"tid": "outro-tenant"}, {"aud": "outro-app"}], ids=["tenant", "app"]
)
def test_token_de_outro_tenant_ou_app_e_recusado(monkeypatch, claims):
    microsoft_returns(monkeypatch, **claims)

    with pytest.raises(InvalidCredentials):
        fetch_identity("codigo")


def test_codigo_invalido_vira_credencial_invalida(monkeypatch):
    microsoft_fails(monkeypatch, http_error(400, {"error": "invalid_grant"}))

    with pytest.raises(InvalidCredentials):
        fetch_identity("codigo")


@pytest.mark.parametrize(
    "error",
    [http_error(401, {"error": "invalid_client"}), TimeoutError()],
    ids=["configuracao", "rede"],
)
def test_falha_da_microsoft_vira_servico_indisponivel(monkeypatch, error):
    microsoft_fails(monkeypatch, error)

    with pytest.raises(ExternalServiceError):
        fetch_identity("codigo")


def test_sem_configuracao_nao_chama_a_microsoft(settings):
    settings.MICROSOFT_CLIENT_ID = ""

    with pytest.raises(ExternalServiceError):
        fetch_identity("codigo")


# Regra do domínio (ensure_microsoft_domain)


@pytest.mark.parametrize(
    ("email", "role"),
    [("ana@a.edu.br", UserRole.STUDENT), ("bia@P.EDU.BR", UserRole.TEACHER)],
)
def test_dominio_define_o_papel(domains, email, role):
    assert ensure_microsoft_domain(email) == role


@pytest.mark.parametrize("email", ["x@gmail.com", "x@admin.edu.br", "x@inativo.br"])
def test_dominio_desconhecido_inativo_ou_de_outro_papel_e_recusado(domains, email):
    EmailDomainFactory(name="inativo.br", active=False)

    with pytest.raises(DomainRoleMismatch):
        ensure_microsoft_domain(email)


# Caso de uso (authenticate_microsoft_user)


def authenticate(email="ana@a.edu.br", microsoft_id=OID):
    return authenticate_microsoft_user(
        microsoft_id=microsoft_id, email=email, name="Ana"
    )


def test_primeiro_acesso_cria_o_usuario_sem_senha_e_sem_perfil(domains):
    user = authenticate()

    assert (user.email, user.role, user.microsoft_id) == (
        "ana@a.edu.br",
        UserRole.STUDENT,
        OID,
    )
    assert user.email_confirmed
    assert not user.has_usable_password()
    assert not hasattr(user, "student")


def test_acesso_seguinte_encontra_pelo_oid_mesmo_com_outro_email(domains):
    user = authenticate()

    assert authenticate(email="novo@a.edu.br") == user
    assert User.objects.count() == 1


def test_usuario_ja_cadastrado_pelo_email_e_vinculado(domains):
    teacher = UserFactory(email="bia@p.edu.br", role=UserRole.TEACHER)

    assert authenticate(email="bia@p.edu.br") == teacher
    teacher.refresh_from_db()
    assert teacher.microsoft_id == OID


@pytest.mark.parametrize(("current", "expected"), [("", "Ana"), ("Bia", "Bia")])
def test_vinculo_preenche_so_o_nome_vazio(domains, current, expected):
    user = UserFactory(email="ana@a.edu.br", name=current)

    authenticate()

    user.refresh_from_db()
    assert user.name == expected


def test_email_de_outra_identidade_microsoft_e_recusado(domains):
    UserFactory(email="ana@a.edu.br", microsoft_id="outro-oid")

    with pytest.raises(MicrosoftIdentityMismatch):
        authenticate()


def test_usuario_do_email_com_outro_papel_e_recusado(domains):
    UserFactory(email="ana@a.edu.br", role=UserRole.TEACHER)

    with pytest.raises(DomainRoleMismatch):
        authenticate()


def test_dominio_nao_institucional_e_recusado(domains):
    with pytest.raises(DomainRoleMismatch):
        authenticate(email="ana@gmail.com")

    assert not User.objects.exists()


def test_usuario_inativo_nao_entra_nem_e_vinculado(domains):
    UserFactory(email="ana@a.edu.br", is_active=False)

    with pytest.raises(InactiveAccount):
        authenticate()

    assert not User.objects.filter(microsoft_id=OID).exists()


# POST /api/auth/sessions/microsoft

URL = "/api/auth/sessions/microsoft"


def post(code="codigo"):
    client = APIClient()
    return client, client.post(URL, {"code": code}, format="json")


def test_primeiro_acesso_cria_a_sessao_com_perfil_pendente(domains, monkeypatch):
    microsoft_returns(monkeypatch)

    client, resposta = post()

    assert resposta.status_code == 200
    user = User.objects.get()
    assert resposta.data == {
        "user_id": user.pk,
        "name": "Ana",
        "email": "ana@a.edu.br",
        "role": UserRole.STUDENT,
        "profile_completed": False,
    }
    assert client.session["_auth_user_id"] == str(user.pk)


def test_aluno_com_perfil_recebe_profile_completed(domains, monkeypatch):
    StudentFactory(user__email="ana@a.edu.br", user__microsoft_id=OID)
    microsoft_returns(monkeypatch)

    _, resposta = post()

    assert resposta.data["profile_completed"] is True


@pytest.mark.django_db
def test_codigo_invalido_recebe_401_sem_sessao(monkeypatch):
    microsoft_fails(monkeypatch, http_error(400, {"error": "invalid_grant"}))

    client, resposta = post()

    assert resposta.status_code == 401
    assert resposta.data["error"]["code"] == "invalid_credentials"
    assert "_auth_user_id" not in client.session


def test_dominio_nao_institucional_recebe_403(domains, monkeypatch):
    microsoft_returns(monkeypatch, preferred_username="ana@gmail.com")

    _, resposta = post()

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "domain_role_mismatch"


def test_identidade_divergente_recebe_409(domains, monkeypatch):
    UserFactory(email="ana@a.edu.br", microsoft_id="outro-oid")
    microsoft_returns(monkeypatch)

    _, resposta = post()

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "microsoft_identity_mismatch"


@pytest.mark.django_db
def test_sem_codigo_recebe_400():
    _, resposta = post(code="")

    assert resposta.status_code == 400


@pytest.mark.django_db
def test_exige_csrf(monkeypatch):
    microsoft_returns(monkeypatch)
    client = APIClient(enforce_csrf_checks=True)

    resposta = client.post(URL, {"code": "codigo"}, format="json")

    assert resposta.status_code == 403
