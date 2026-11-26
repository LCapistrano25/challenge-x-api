"""As respostas de support seguem o contrato (docs/api/openapi.yaml)."""

import pytest

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.support.tests.test_api import auth_client

pytestmark = pytest.mark.django_db


def test_fluxo_completo_de_chamados_segue_o_contrato():
    student = UserFactory(role=UserRole.STUDENT)
    admin = UserFactory(role=UserRole.ADMIN)

    student_client = auth_client(student)
    admin_client = auth_client(admin)

    # 1. Solicitante cria, lista e consulta o chamado
    created = student_client.post(
        "/api/support/tickets",
        {
            "title": "Correção de matrícula",
            "description": "Minha matrícula foi cadastrada incorretamente.",
        },
        format="json",
    )
    assert created.status_code == 201
    assert mismatches(created.json(), schema("SupportTicket")) == []
    ticket_id = created.json()["id"]

    my_list = student_client.get("/api/support/tickets")
    assert my_list.status_code == 200
    assert mismatches(my_list.json(), schema("PaginatedSupportTicket")) == []

    my_detail = student_client.get(f"/api/support/tickets/{ticket_id}")
    assert my_detail.status_code == 200
    assert mismatches(my_detail.json(), schema("SupportTicket")) == []

    # 2. Admin lista (assigned_to = null) e consulta
    admin_list = admin_client.get("/api/admin/support/tickets")
    assert admin_list.status_code == 200
    assert mismatches(admin_list.json(), schema("PaginatedSupportTicketAdmin")) == []

    admin_detail = admin_client.get(f"/api/admin/support/tickets/{ticket_id}")
    assert admin_detail.status_code == 200
    assert mismatches(admin_detail.json(), schema("SupportTicketAdmin")) == []

    # 3. Admin atende (assigned_to preenchido e status CLOSED)
    updated = admin_client.patch(
        f"/api/admin/support/tickets/{ticket_id}",
        {
            "status": "CLOSED",
            "priority": "HIGH",
            "support_response": "Solicitação encerrada após análise.",
            "assigned_to": admin.id,
        },
        format="json",
    )
    assert updated.status_code == 200
    assert mismatches(updated.json(), schema("SupportTicketAdmin")) == []

    # 4. Transição proibida (409) segue o schema Error
    conflict = admin_client.patch(
        f"/api/admin/support/tickets/{ticket_id}",
        {"status": "IN_PROGRESS"},
        format="json",
    )
    assert conflict.status_code == 409
    assert mismatches(conflict.json(), schema("Error")) == []
