from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.support.models import SupportTicket


def list_my_tickets(
    *,
    user: User,
    status: str | None = None,
) -> QuerySet[SupportTicket]:
    qs = SupportTicket.objects.filter(requester=user)
    if status:
        qs = qs.filter(status=status)
    return qs


def get_my_ticket(*, user: User, ticket_id) -> SupportTicket | None:
    return SupportTicket.objects.filter(requester=user, pk=ticket_id).first()


def list_admin_tickets(
    *,
    status: str | None = None,
    priority: str | None = None,
    assigned_to: int | None = None,
    search: str | None = None,
) -> QuerySet[SupportTicket]:
    qs = SupportTicket.objects.select_related("requester", "assigned_to")
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if assigned_to is not None:
        qs = qs.filter(assigned_to_id=assigned_to)
    if search:
        term = search.strip()
        if term:
            qs = qs.filter(
                Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(requester__name__icontains=term)
                | Q(requester__email__icontains=term)
            )
    return qs


def get_admin_ticket(*, ticket_id) -> SupportTicket | None:
    return (
        SupportTicket.objects.select_related("requester", "assigned_to")
        .filter(pk=ticket_id)
        .first()
    )
