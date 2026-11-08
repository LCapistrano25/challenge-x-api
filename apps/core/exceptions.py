from http import HTTPStatus


class AppError(Exception):
    """Erro esperado da aplicação, com código estável para a API.

    `http_status` vem da biblioteca padrão para o domínio não depender do DRF.
    A filha só redefine o status quando foge do padrão da base.
    """

    code = "app_error"
    default_message = "Não foi possível concluir a operação."
    http_status = HTTPStatus.BAD_REQUEST

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)


class BusinessRuleViolation(AppError):
    """Violação de regra de negócio."""

    code = "business_rule_violation"
    default_message = "Operação não permitida."
    http_status = HTTPStatus.CONFLICT


class ExternalServiceError(AppError):
    """Serviço externo (e-mail, armazenamento) indisponível."""

    code = "external_service_error"
    default_message = "Serviço temporariamente indisponível."
    http_status = HTTPStatus.SERVICE_UNAVAILABLE
