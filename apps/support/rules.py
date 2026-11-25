from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.models import User
from apps.support.enums import SupportTicketPriority, SupportTicketStatus
from apps.support.exceptions import InvalidStatusTransition

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    SupportTicketStatus.OPEN: {
        SupportTicketStatus.IN_PROGRESS,
        SupportTicketStatus.RESOLVED,
        SupportTicketStatus.CLOSED,
    },
    SupportTicketStatus.IN_PROGRESS: {
        SupportTicketStatus.RESOLVED,
        SupportTicketStatus.CLOSED,
    },
    SupportTicketStatus.RESOLVED: {
        SupportTicketStatus.IN_PROGRESS,
        SupportTicketStatus.CLOSED,
    },
    SupportTicketStatus.CLOSED: set(),
    SupportTicketStatus.WAITING_USER: set(),
}


def ensure_actor_can_open_ticket(actor: User) -> None:
    if actor.role not in {UserRole.STUDENT, UserRole.TEACHER}:
        raise ValidationError(
            {"actor": "Apenas alunos e professores podem abrir chamados."}
        )


def ensure_valid_status_transition(current_status: str, new_status: str) -> None:
    if new_status == SupportTicketStatus.WAITING_USER:
        raise InvalidStatusTransition("O status WAITING_USER não é utilizado.")
    if new_status == current_status:
        return
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise InvalidStatusTransition()


def ensure_valid_priority(priority: str) -> None:
    if priority not in SupportTicketPriority.values:
        raise ValidationError({"priority": "Prioridade inválida."})


def ensure_closed_has_response(status: str, support_response: str | None) -> None:
    if status == SupportTicketStatus.CLOSED and not (support_response or "").strip():
        raise ValidationError(
            {
                "support_response": (
                    "Informe a resposta do suporte para encerrar o chamado."
                )
            }
        )


def ensure_valid_assignee(assigned_to: User | None) -> None:
    if assigned_to is None:
        return
    if assigned_to.role != UserRole.ADMIN or not assigned_to.is_active:
        raise ValidationError(
            {
                "assigned_to": (
                    "O responsável pelo chamado deve ser um administrador ativo."
                )
            }
        )
