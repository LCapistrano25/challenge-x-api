"""Atualizar cadastro de avaliador externo pelo administrador (RFXX). RF11."""

from django.db import transaction

from apps.accounts.exceptions import UserNotFound
from apps.accounts.models import ExternalReviewer, User
from apps.accounts.rules import ensure_actor_is_admin


@transaction.atomic
def update_external_reviewer(
    *,
    actor: User,
    user_id: int,
    name: str | None = None,
    institution: str | None = None,
) -> ExternalReviewer:
    """Atualiza nome e instituição; institution vazia limpa o campo."""
    ensure_actor_is_admin(actor)
    reviewer = ExternalReviewer.objects.select_related("user").filter(pk=user_id)
    reviewer = reviewer.first()
    if reviewer is None:
        raise UserNotFound()

    if name is not None:
        reviewer.user.name = name
        reviewer.user.save(update_fields=["name", "updated_at"])
    if institution is not None:
        reviewer.institution = institution
    reviewer.save()
    return reviewer
