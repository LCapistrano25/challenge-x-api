from uuid import UUID

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.notifications.models import Notification


@transaction.atomic
def mark_notification_as_read(*, actor, notification_id: UUID) -> Notification:
    """Preenche read_at de uma notificação do próprio usuário (idempotente)."""
    notification = get_object_or_404(Notification, id=notification_id, user=actor)

    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])

    return notification
