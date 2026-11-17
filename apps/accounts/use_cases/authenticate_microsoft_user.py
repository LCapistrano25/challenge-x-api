"""UC — Entrar com a conta Microsoft. RF18, RF36, RN02."""

from django.db import transaction

from apps.accounts.exceptions import (
    DomainRoleMismatch,
    InactiveAccount,
    MicrosoftIdentityMismatch,
)
from apps.accounts.models import User
from apps.accounts.rules import ensure_microsoft_domain


@transaction.atomic
def authenticate_microsoft_user(*, microsoft_id: str, email: str, name: str) -> User:
    """Encontra ou cria o aluno ou professor que entrou pela Microsoft.

    No primeiro acesso cria só o User, com o papel do domínio; o perfil (student,
    teacher) vem depois (RF19, RF36.1). Quem já existe pelo e-mail, como o
    professor cadastrado pelo administrador, é vinculado à identidade.
    Levanta DomainRoleMismatch, MicrosoftIdentityMismatch ou InactiveAccount.
    """
    user = User.objects.filter(microsoft_id=microsoft_id).first()

    if user is None:
        role = ensure_microsoft_domain(email)
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User(email=email, name=name, role=role, email_confirmed=True)
            # Sem senha: o login com senha recusa aluno e professor.
            user.set_unusable_password()
        elif user.microsoft_id:
            raise MicrosoftIdentityMismatch()
        elif user.role != role:
            raise DomainRoleMismatch()
        user.microsoft_id = microsoft_id
        # Cadastro antigo sem nome (ex.: seed) ganha o da conta institucional.
        user.name = user.name or name
        user.save()

    if not user.is_active:
        raise InactiveAccount()
    return user
