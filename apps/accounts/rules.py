from django.apps import apps
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole

# Os models importam estas regras; por isso elas pegam os models pelo registro
# do Django (como a FK por string), sem import que fecharia o ciclo.

# Perfil (related_name no User) que cada papel exige; ADMIN não tem perfil.
PROFILE_BY_ROLE = {
    UserRole.STUDENT: "student",
    UserRole.TEACHER: "teacher",
    UserRole.EXTERNAL_REVIEWER: "external_reviewer",
}


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
    domains = apps.get_model("accounts", "EmailDomain").objects

    try:
        domain = domains.get(name__iexact=domain_name, active=True)
    except domains.model.DoesNotExist:
        raise InvalidEmailDomain("E-mail fora dos domínios autorizados.") from None

    if domain.role != role:
        raise DomainRoleMismatch("Perfil não autorizado para este domínio.")


def has_role_profile(user) -> bool:
    """O papel do usuário vem acompanhado do perfil que ele exige."""
    profile = PROFILE_BY_ROLE.get(user.role)
    return profile is None or hasattr(user, profile)


def ensure_role_change_allowed(user) -> None:
    """Impede trocar o papel de quem já tem perfil: o perfil antigo ficaria órfão."""
    users = apps.get_model("accounts", "User").objects
    current_role = users.filter(pk=user.pk).values_list("role", flat=True).first()
    if current_role in (None, user.role):
        return
    if any(hasattr(user, profile) for profile in PROFILE_BY_ROLE.values()):
        raise ValidationError(
            {"role": "O usuário já tem perfil; o papel não pode ser trocado."}
        )
