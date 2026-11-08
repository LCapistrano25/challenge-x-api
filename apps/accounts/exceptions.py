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
