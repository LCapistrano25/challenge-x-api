"""UC06 — Exclui um critério de avaliação sem vínculo com etapa (RF06)."""

from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import CriterionLinkedToStage
from apps.editions.models import Criterion, Edition
from apps.editions.rules import ensure_edition_not_closed
from apps.editions.selectors import get_locked_criterion


@transaction.atomic
def delete_criterion(*, actor: User, criterion: Criterion) -> None:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=criterion.edition_id)
    ensure_edition_not_closed(edition)
    criterion = get_locked_criterion(criterion.pk)
    try:
        criterion.delete()
    except ProtectedError as error:
        raise CriterionLinkedToStage() from error
