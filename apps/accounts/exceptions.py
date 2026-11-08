from http import HTTPStatus

from apps.core.exceptions import BusinessRuleViolation


class InvalidEmailDomain(BusinessRuleViolation):
    code = "invalid_email_domain"
    default_message = "E-mail fora dos domínios autorizados."
    http_status = HTTPStatus.BAD_REQUEST


class DomainRoleMismatch(BusinessRuleViolation):
    code = "domain_role_mismatch"
    default_message = "Perfil não autorizado para este domínio."
    http_status = HTTPStatus.FORBIDDEN


# As falhas do login são exceções da aplicação, e não AuthenticationFailed do DRF:
# sem authentication_classes, o DRF troca o 401 por 403.
class InvalidCredentials(BusinessRuleViolation):
    code = "invalid_credentials"
    default_message = "Credenciais inválidas."
    http_status = HTTPStatus.UNAUTHORIZED


class EmailNotConfirmed(BusinessRuleViolation):
    code = "email_not_confirmed"
    default_message = "Confirme seu e-mail antes de entrar."
    http_status = HTTPStatus.FORBIDDEN


class InstitutionalDomainDenied(BusinessRuleViolation):
    code = "institutional_domain_denied"
    default_message = "Domínio institucional não autorizado."
    http_status = HTTPStatus.FORBIDDEN
