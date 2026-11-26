import logging

from django.db import transaction

from apps.notifications.models import Notification, NotificationType

logger = logging.getLogger(__name__)


def create_notification(
    *,
    user,
    notification_type: NotificationType,
    title: str,
    message: str,
    link: str | None = None,
) -> Notification | None:
    """Cria uma notificação para um usuário.

    Falhas são registradas em log e não interrompem o caso de uso chamador.
    """
    try:
        with transaction.atomic():
            return Notification.objects.create(
                user=user,
                type=notification_type,
                title=title,
                message=message,
                link=link,
            )
    except Exception:
        logger.exception(
            "Falha ao criar notificação (type=%s, user_id=%s, title=%r)",
            notification_type,
            getattr(user, "id", None),
            title,
        )
        return None
