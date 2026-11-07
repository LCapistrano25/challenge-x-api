class DomainError(Exception):
    """Violação de regra de negócio. A API decide o status HTTP."""

    code = "domain_error"
    default_message = "Operação não permitida."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)