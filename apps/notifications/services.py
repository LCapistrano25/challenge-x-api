from apps.notifications.models import Notification, NotificationType


def create_notification(
    *,
    user,
    notification_type: NotificationType,
    title: str,
    message: str,
    link: str | None = None,
) -> Notification:
    """Cria uma notificação para um usuário."""
    return Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        message=message,
        link=link,
    )
