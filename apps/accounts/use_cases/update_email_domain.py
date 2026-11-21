"""UC02 — Editar e ativar/desativar domínio institucional de e-mail. RF02, RN02."""

from django.db import IntegrityError, transaction

from apps.accounts.exceptions import EmailDomainNotFound, EmailDomainTaken
from apps.accounts.models import EmailDomain, User
from apps.accounts.rules import (
    ensure_actor_is_admin,
    ensure_email_domain_role_allowed,
    ensure_valid_email_domain_name,
)


@transaction.atomic
def update_email_domain(
    *,
    actor: User,
    domain_id: int,
    name: str | None = None,
    role: str | None = None,
    active: bool | None = None,
) -> EmailDomain:
    """Edita nome, perfil ou status de ativação de um domínio institucional (UC02)."""
    ensure_actor_is_admin(actor)

    try:
        domain = EmailDomain.objects.get(pk=domain_id)
    except EmailDomain.DoesNotExist:
        raise EmailDomainNotFound() from None

    update_fields: list[str] = []

    if name is not None:
        normalized = ensure_valid_email_domain_name(name)
        if (
            EmailDomain.objects.filter(name__iexact=normalized)
            .exclude(pk=domain.pk)
            .exists()
        ):
            raise EmailDomainTaken()
        domain.name = normalized
        update_fields.append("name")

    if role is not None:
        ensure_email_domain_role_allowed(role)
        domain.role = role
        update_fields.append("role")

    if active is not None:
        domain.active = active
        update_fields.append("active")

    if update_fields:
        try:
            domain.save(update_fields=[*update_fields, "updated_at"])
        except IntegrityError:
            raise EmailDomainTaken() from None

    return domain
