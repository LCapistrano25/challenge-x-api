from apps.accounts.models import EmailDomain


class InvalidEmailDomain(Exception):
    pass


class DomainRoleMismatch(Exception):
    pass


def ensure_institutional_domain(email: str, role: str) -> None:
    """Exige domínio ativo associado ao perfil informado (RF02, RN02 do Admin)."""
    email = email.strip().lower()

    if "@" not in email:
        raise InvalidEmailDomain("E-mail inválido.")

    domain_name = email.rsplit("@", 1)[1]

    try:
        domain = EmailDomain.objects.get(name__iexact=domain_name, active=True)
    except EmailDomain.DoesNotExist:
        raise InvalidEmailDomain("E-mail fora dos domínios autorizados.") from None

    if domain.role != role:
        raise DomainRoleMismatch("Perfil não autorizado para este domínio.")
