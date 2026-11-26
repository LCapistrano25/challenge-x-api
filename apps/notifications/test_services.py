import logging
from unittest.mock import patch

import pytest
from django.db import DatabaseError, transaction

from apps.accounts.factories import UserFactory
from apps.notifications.models import Notification, NotificationType
from apps.notifications.services import create_notification

pytestmark = pytest.mark.django_db


def test_create_notification_sucesso():
    user = UserFactory()

    notif = create_notification(
        user=user,
        notification_type=NotificationType.TEAM,
        title="Convite",
        message="Você foi convidado.",
        link="/convites/1",
    )

    assert notif is not None
    assert Notification.objects.filter(id=notif.id, user=user).exists()


def test_create_notification_falha_vira_log_e_nao_quebra_transacao(caplog):
    user = UserFactory()

    with (
        caplog.at_level(logging.ERROR, logger="apps.notifications.services"),
        patch(
            "apps.notifications.services.Notification.objects.create",
            side_effect=DatabaseError("erro simulado"),
        ),
        transaction.atomic(),
    ):
        result = create_notification(
            user=user,
            notification_type=NotificationType.DELIVERABLE,
            title="Entrega",
            message="Nova entrega registrada.",
        )
        # Garante que a transação externa continua íntegra
        assert Notification.objects.count() == 0

    assert result is None
    assert "Falha ao criar notificação" in caplog.text
