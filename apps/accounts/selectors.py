"""Consultas de leitura de accounts (RF02)."""

from django.db.models import QuerySet

from apps.accounts.models import EmailDomain


def list_email_domains(
    *, active: bool | None = None, role: str | None = None
) -> QuerySet[EmailDomain]:
    """Lista os domínios institucionais ordenados por nome."""
    queryset = EmailDomain.objects.order_by("name")
    if active is not None:
        queryset = queryset.filter(active=active)
    if role:
        queryset = queryset.filter(role=role)
    return queryset
