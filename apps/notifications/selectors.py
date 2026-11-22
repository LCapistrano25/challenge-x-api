from django.db.models import QuerySet

from apps.notifications.models import Notification


def list_user_notifications(user) -> QuerySet[Notification]:
    """Retorna as notificações do usuário ordenadas da
    mais recente para a mais antiga."""
    return Notification.objects.filter(user=user).order_by("-created_at")
