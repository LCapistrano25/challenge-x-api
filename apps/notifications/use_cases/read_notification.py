from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.notifications.models import Notification


@transaction.atomic
def mark_notification_as_read(actor, notification_id: int) -> Notification:
    """
    Marca uma notificação do usuário como lida.
    """
    # 1. Busca a notificação garantindo que pertence ao usuário (actor).
    # Se não for dele ou não existir, o Django lança Http404 e o
    #  DRF cuida de devolver a resposta 404 correta.
    notification = get_object_or_404(Notification, id=notification_id, user=actor)

    # 2. Se já estiver lida, não faz nada. Se não estiver, atualiza.
    if not notification.read:
        notification.read = True
        notification.save(update_fields=["read"])

    return notification
