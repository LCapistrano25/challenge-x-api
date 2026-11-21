"""UC02 — Cadastrar domínio institucional de e-mail. RF02, RN02."""

from django.db import IntegrityError, transaction

from apps.accounts.exceptions import EmailDomainTaken
from apps.accounts.models import EmailDomain, User
from apps.accounts.rules import (
    ensure_actor_is_admin,
    ensure_email_domain_role_allowed,
    ensure_valid_email_domain_name,
)


@transaction.atomic
def create_email_domain(
    *, actor: User, name: str, role: str, active: bool = True
) -> EmailDomain:
    """Cadastra um domínio de e-mail institucional ligado a um perfil (UC02)."""
    ensure_actor_is_admin(actor)
    normalized = ensure_valid_email_domain_name(name)
    ensure_email_domain_role_allowed(role)

    if EmailDomain.objects.filter(name__iexact=normalized).exists():
        raise EmailDomainTaken()

    try:
        return EmailDomain.objects.create(name=normalized, role=role, active=active)
    except IntegrityError:
        raise EmailDomainTaken() from None
