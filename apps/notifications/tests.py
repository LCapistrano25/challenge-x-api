# Create your tests here.
import uuid
from datetime import timedelta

import pytest
from django.http import Http404
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.notifications.models import Notification, NotificationType
from apps.notifications.use_cases.read_notification import mark_notification_as_read

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def make_notification(user, *, read_at=None, title="Aviso"):
    return Notification.objects.create(
        user=user,
        type=NotificationType.TEAM,
        title=title,
        message="Mensagem de teste.",
        link="/convites/1",
        read_at=read_at,
    )


# --- Testes do caso de uso ---


def test_mark_notification_as_read_preenche_read_at():
    user = UserFactory()
    notif = make_notification(user)

    result = mark_notification_as_read(actor=user, notification_id=notif.id)

    assert result.read_at is not None
    notif.refresh_from_db()
    assert notif.read_at is not None


def test_mark_notification_as_read_e_idempotente():
    user = UserFactory()
    original_read_at = timezone.now()
    notif = make_notification(user, read_at=original_read_at)

    result = mark_notification_as_read(actor=user, notification_id=notif.id)

    assert result.read_at == original_read_at


def test_mark_notification_as_read_de_outro_usuario_lanca_404():
    dono = UserFactory()
    outro = UserFactory()
    notif = make_notification(dono)

    with pytest.raises(Http404):
        mark_notification_as_read(actor=outro, notification_id=notif.id)


# --- Testes da API e contrato ---


def test_listar_notificacoes_sem_login_retorna_401(api_client):
    response = api_client.get("/api/notifications")
    assert response.status_code == 401


def test_marcar_como_lida_sem_login_retorna_401(api_client):
    response = api_client.post(f"/api/notifications/{uuid.uuid4()}/read")
    assert response.status_code == 401


def test_listar_notificacoes_segue_contrato_e_isola_usuario(api_client):
    user = UserFactory()
    outro = UserFactory()
    n1 = make_notification(user, title="Primeira")
    n2 = make_notification(user, title="Segunda")
    make_notification(outro, title="De outro usuário")
    # As duas podem nascer no mesmo instante; a mais antiga fica explícita.
    Notification.objects.filter(pk=n1.pk).update(
        created_at=n2.created_at - timedelta(seconds=1)
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/notifications")

    assert response.status_code == 200
    body = response.json()
    assert mismatches(body, schema("PaginatedNotification")) == []
    assert body["count"] == 2
    assert [item["id"] for item in body["results"]] == [str(n2.id), str(n1.id)]


def test_listar_notificacoes_filtro_unread(api_client):
    user = UserFactory()
    nao_lida = make_notification(user, read_at=None)
    make_notification(user, read_at=timezone.now())

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/notifications?unread=true")

    assert response.status_code == 200
    body = response.json()
    assert mismatches(body, schema("PaginatedNotification")) == []
    assert [item["id"] for item in body["results"]] == [str(nao_lida.id)]


def test_filtro_unread_invalido_retorna_400(api_client):
    api_client.force_authenticate(user=UserFactory())

    response = api_client.get("/api/notifications?unread=abc")

    assert response.status_code == 400
    assert response.json()["error"]["details"].keys() == {"unread"}


def test_marcar_notificacao_como_lida_segue_contrato(api_client):
    user = UserFactory()
    notif = make_notification(user)

    api_client.force_authenticate(user=user)
    response = api_client.post(f"/api/notifications/{notif.id}/read")

    assert response.status_code == 200
    body = response.json()
    assert mismatches(body, schema("Notification")) == []
    assert body["read_at"] is not None


def test_marcar_notificacao_de_outro_usuario_retorna_404(api_client):
    dono = UserFactory()
    outro = UserFactory()
    notif = make_notification(dono)

    api_client.force_authenticate(user=outro)
    response = api_client.post(f"/api/notifications/{notif.id}/read")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
