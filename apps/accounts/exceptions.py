from http import HTTPStatus

from apps.core.exceptions import DomainError


class InvalidEmailDomain(DomainError):
    code = "invalid_email_domain"
    default_message = "E-mail fora dos domínios autorizados."
    http_status = HTTPStatus.BAD_REQUEST


class DomainRoleMismatch(DomainError):
    code = "domain_role_mismatch"
    default_message = "Perfil não autorizado para este domínio."
    http_status = HTTPStatus.FORBIDDEN


# As falhas do login são exceções da aplicação, e não AuthenticationFailed do DRF:
# sem authentication_classes, o DRF troca o 401 por 403.
class InvalidCredentials(DomainError):
    code = "invalid_credentials"
    default_message = "Credenciais inválidas."
    http_status = HTTPStatus.UNAUTHORIZED


class EmailNotConfirmed(DomainError):
    code = "email_not_confirmed"
    default_message = "Confirme seu e-mail antes de entrar."
    http_status = HTTPStatus.FORBIDDEN


class InstitutionalDomainDenied(DomainError):
    code = "institutional_domain_denied"
    default_message = "Domínio institucional não autorizado."
    http_status = HTTPStatus.FORBIDDEN


class InvalidConfirmationToken(DomainError):
    code = "invalid_confirmation_token"
    default_message = "Token de confirmação inválido."
    http_status = HTTPStatus.BAD_REQUEST


class ConfirmationTokenExpired(InvalidConfirmationToken):
    code = "confirmation_token_expired"
    default_message = "O link de confirmação expirou."
