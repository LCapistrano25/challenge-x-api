from django.db.models import QuerySet

from apps.notifications.models import Notification


def list_user_notifications(
    *, user, unread_only: bool = False
) -> QuerySet[Notification]:
    """Lista notificações do usuário, das mais recentes para as mais antigas."""
    qs = Notification.objects.filter(user=user)
    if unread_only:
        qs = qs.filter(read_at__isnull=True)
    return qs.order_by("-created_at")
