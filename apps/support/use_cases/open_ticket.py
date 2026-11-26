"""RFXX — Abrir chamado de correção cadastral."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.support.enums import SupportTicketPriority, SupportTicketStatus
from apps.support.models import SupportTicket
from apps.support.rules import ensure_actor_can_open_ticket


@transaction.atomic
def open_ticket(
    *,
    actor: User,
    title: str,
    description: str,
) -> SupportTicket:
    """Abre um chamado vinculado ao usuário autenticado (aluno ou professor)."""
    ensure_actor_can_open_ticket(actor)

    clean_title = (title or "").strip()
    clean_description = (description or "").strip()

    errors: dict[str, str] = {}
    if not clean_title:
        errors["title"] = "Informe o título do chamado."
    elif len(clean_title) > 150:
        errors["title"] = "O título deve ter no máximo 150 caracteres."
    if not clean_description:
        errors["description"] = "Informe a descrição do chamado."
    if errors:
        raise ValidationError(errors)

    return SupportTicket.objects.create(
        requester=actor,
        title=clean_title,
        description=clean_description,
        status=SupportTicketStatus.OPEN,
        priority=SupportTicketPriority.MEDIUM,
    )
