from apps.core.exceptions import BusinessRuleViolation


class SupportError(BusinessRuleViolation):
    """Base das violações de regra de negócio do app support."""

    code = "support_error"
    default_message = "Operação não permitida para o chamado."


class InvalidStatusTransition(SupportError):
    code = "invalid_status_transition"
    default_message = "Transição de status não permitida."
