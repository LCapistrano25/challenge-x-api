import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.support.enums import SupportTicketPriority, SupportTicketStatus
from apps.support.factories import SupportTicketFactory

pytestmark = pytest.mark.django_db


def auth_client(user=None) -> APIClient:
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


# Autenticação (401) e autorização (403)


def test_rotas_exigem_autenticacao():
    ticket = SupportTicketFactory()
    client = auth_client()

    assert client.post("/api/support/tickets", {}, format="json").status_code == 401
    assert client.get("/api/support/tickets").status_code == 401
    assert client.get(f"/api/support/tickets/{ticket.id}").status_code == 401
    assert client.get("/api/admin/support/tickets").status_code == 401
    assert client.get(f"/api/admin/support/tickets/{ticket.id}").status_code == 401
    assert (
        client.patch(
            f"/api/admin/support/tickets/{ticket.id}", {}, format="json"
        ).status_code
        == 401
    )


def test_admin_nao_acessa_rotas_do_solicitante():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()
    client = auth_client(admin)

    assert (
        client.post(
            "/api/support/tickets",
            {"title": "T", "description": "D"},
            format="json",
        ).status_code
        == 403
    )
    assert client.get("/api/support/tickets").status_code == 403
    assert client.get(f"/api/support/tickets/{ticket.id}").status_code == 403


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.TEACHER])
def test_aluno_e_professor_nao_acessam_rotas_admin(role):
    user = UserFactory(role=role)
    ticket = SupportTicketFactory(requester=user)
    client = auth_client(user)

    assert client.get("/api/admin/support/tickets").status_code == 403
    assert client.get(f"/api/admin/support/tickets/{ticket.id}").status_code == 403
    assert (
        client.patch(
            f"/api/admin/support/tickets/{ticket.id}",
            {"priority": "HIGH"},
            format="json",
        ).status_code
        == 403
    )


# Rotas do solicitante (/api/support/tickets)


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.TEACHER])
def test_criar_chamado_retorna_201(role):
    user = UserFactory(role=role)
    client = auth_client(user)

    resp = client.post(
        "/api/support/tickets",
        {
            "title": "Correção de matrícula",
            "description": "Minha matrícula foi cadastrada errada.",
        },
        format="json",
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Correção de matrícula"
    assert data["status"] == SupportTicketStatus.OPEN
    assert data["priority"] == SupportTicketPriority.MEDIUM
    assert data["support_response"] is None
    assert data["resolved_at"] is None


def test_listar_meus_chamados_filtra_por_dono_e_status():
    student = UserFactory(role=UserRole.STUDENT)
    other = UserFactory(role=UserRole.STUDENT)
    t_open = SupportTicketFactory(requester=student, status=SupportTicketStatus.OPEN)
    SupportTicketFactory(requester=student, status=SupportTicketStatus.RESOLVED)
    SupportTicketFactory(requester=other, status=SupportTicketStatus.OPEN)

    client = auth_client(student)
    resp = client.get("/api/support/tickets?status=OPEN")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["id"] == str(t_open.id)


def test_consultar_meu_chamado_e_404_para_outro_usuario():
    student = UserFactory(role=UserRole.STUDENT)
    other = UserFactory(role=UserRole.STUDENT)
    own = SupportTicketFactory(requester=student)
    foreign = SupportTicketFactory(requester=other)

    client = auth_client(student)
    assert client.get(f"/api/support/tickets/{own.id}").status_code == 200
    assert client.get(f"/api/support/tickets/{foreign.id}").status_code == 404


# Rotas administrativas (/api/admin/support/tickets)


def test_admin_lista_e_filtra_chamados():
    admin = UserFactory(role=UserRole.ADMIN)
    t1 = SupportTicketFactory(
        title="Erro no nome",
        status=SupportTicketStatus.IN_PROGRESS,
        priority=SupportTicketPriority.HIGH,
        assigned_to=admin,
    )
    SupportTicketFactory(
        title="Outro chamado",
        status=SupportTicketStatus.OPEN,
        priority=SupportTicketPriority.LOW,
    )

    client = auth_client(admin)
    resp = client.get(
        f"/api/admin/support/tickets?status=IN_PROGRESS&priority=HIGH"
        f"&assigned_to={admin.id}&search=nome"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["id"] == str(t1.id)
    assert body["results"][0]["requester"]["user_id"] == t1.requester_id
    assert body["results"][0]["assigned_to"]["user_id"] == admin.id


def test_admin_consulta_chamado_e_404():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()
    client = auth_client(admin)

    assert client.get(f"/api/admin/support/tickets/{ticket.id}").status_code == 200
    assert client.get(f"/api/admin/support/tickets/{uuid.uuid4()}").status_code == 404


def test_admin_atende_chamado_via_patch():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()
    client = auth_client(admin)

    resp = client.patch(
        f"/api/admin/support/tickets/{ticket.id}",
        {
            "status": "RESOLVED",
            "priority": "HIGH",
            "support_response": "Cadastro atualizado.",
            "assigned_to": admin.id,
        },
        format="json",
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["priority"] == "HIGH"
    assert data["support_response"] == "Cadastro atualizado."
    assert data["assigned_to"]["user_id"] == admin.id
    assert data["resolved_at"] is not None


def test_admin_patch_transicao_invalida_retorna_409():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory(
        status=SupportTicketStatus.CLOSED,
        support_response="Recusado.",
    )
    client = auth_client(admin)

    resp = client.patch(
        f"/api/admin/support/tickets/{ticket.id}",
        {"status": "IN_PROGRESS"},
        format="json",
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_status_transition"


def test_admin_patch_recusa_corpo_vazio_e_closed_sem_resposta():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()
    client = auth_client(admin)

    assert (
        client.patch(
            f"/api/admin/support/tickets/{ticket.id}", {}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/admin/support/tickets/{ticket.id}",
            {"status": "CLOSED"},
            format="json",
        ).status_code
        == 400
    )
