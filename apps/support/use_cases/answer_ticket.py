"""RFXX — Atender chamado de suporte (administração)."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.notifications.models import NotificationType
from apps.notifications.services import create_notification
from apps.support.enums import SupportTicketStatus
from apps.support.models import SupportTicket
from apps.support.rules import (
    ensure_closed_has_response,
    ensure_valid_assignee,
    ensure_valid_priority,
    ensure_valid_status_transition,
)

UNSET = object()


@transaction.atomic
def answer_ticket(
    *,
    actor: User,
    ticket: SupportTicket,
    status: str | object = UNSET,
    priority: str | object = UNSET,
    support_response: str | None | object = UNSET,
    assigned_to: User | None | object = UNSET,
) -> SupportTicket:
    """Atualiza status, prioridade, responsável e resposta do chamado.

    Notifica o solicitante (SYSTEM) quando o status ou a resposta mudam.
    """
    ensure_actor_is_admin(actor)

    ticket = (
        SupportTicket.objects.select_for_update(of=("self",))
        .select_related("requester", "assigned_to")
        .get(pk=ticket.pk)
    )

    old_status = ticket.status
    old_response = ticket.support_response

    new_status = old_status if status is UNSET else status
    new_priority = ticket.priority if priority is UNSET else priority
    if support_response is UNSET:
        new_response = old_response
    elif support_response is None:
        new_response = None
    else:
        stripped = support_response.strip()
        new_response = stripped if stripped else None

    new_assignee = ticket.assigned_to if assigned_to is UNSET else assigned_to

    ensure_valid_status_transition(old_status, new_status)
    ensure_valid_priority(new_priority)
    ensure_closed_has_response(new_status, new_response)
    ensure_valid_assignee(new_assignee)

    status_changed = new_status != old_status
    response_changed = new_response != old_response

    ticket.status = new_status
    ticket.priority = new_priority
    ticket.support_response = new_response
    ticket.assigned_to = new_assignee

    if new_status in {SupportTicketStatus.RESOLVED, SupportTicketStatus.CLOSED}:
        if status_changed or ticket.resolved_at is None:
            ticket.resolved_at = timezone.now()
    elif new_status == SupportTicketStatus.IN_PROGRESS and status_changed:
        ticket.resolved_at = None

    ticket.save()

    if status_changed or response_changed:
        _notify_ticket_updated(ticket=ticket)

    return ticket


def _notify_ticket_updated(*, ticket: SupportTicket) -> None:
    status_label = SupportTicketStatus(ticket.status).label
    create_notification(
        user=ticket.requester,
        notification_type=NotificationType.SYSTEM,
        title=f"Atualização no chamado: {ticket.title}",
        message=f"Seu chamado foi atualizado para '{status_label}'.",
        link=f"/support/tickets/{ticket.id}",
    )
