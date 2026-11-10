from django.apps import apps
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    DomainRoleMismatch,
    InvalidCredentials,
    InvalidEmailDomain,
    ReviewerNotInCurrentEdition,
)

# Os models importam estas regras; por isso elas pegam os models pelo registro
# do Django (como a FK por string), sem import que fecharia o ciclo.

# Perfil (related_name no User) que cada papel exige; ADMIN não tem perfil.
PROFILE_BY_ROLE = {
    UserRole.STUDENT: "student",
    UserRole.TEACHER: "teacher",
    UserRole.EXTERNAL_REVIEWER: "external_reviewer",
}

# Aluno e professor entram pela Microsoft (RF18, RF36).
PASSWORD_ROLES = {UserRole.ADMIN, UserRole.EXTERNAL_REVIEWER}


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


def ensure_term_within_course(course, term: int) -> None:
    """Exige o período entre 1 e a quantidade de períodos do curso (RN10)."""
    if not 1 <= term <= course.term_count:
        raise ValidationError(
            {"term": f"O período deve estar entre 1 e {course.term_count}."}
        )


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


def ensure_reviewer_in_current_edition(user) -> None:
    """Exige o avaliador externo vinculado à edição vigente, não encerrada (RF41).

    Edição vigente é a publicada (P-41): EditionStatus.PUBLISHED.
    """
    # editions fica acima de accounts: lê pelo registro, sem importar o app.
    links = apps.get_model("editions", "EditionReviewer").objects
    if not links.filter(reviewer__user=user, edition__status="PUBLISHED").exists():
        raise ReviewerNotInCurrentEdition()


def ensure_password_login_allowed(user) -> None:
    """Só administrador e avaliador entram com senha (RF01, RF41).

    user é o resultado do authenticate(): None para credencial errada ou conta
    inativa. Todo motivo sai como o mesmo InvalidCredentials, sem revelar qual.
    """
    if user is None or user.role not in PASSWORD_ROLES:
        raise InvalidCredentials()
    if user.role == UserRole.EXTERNAL_REVIEWER:
        ensure_reviewer_in_current_edition(user)
