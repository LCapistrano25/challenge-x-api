"""Define as ODS habilitadas na edição (RF04, RN09)."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.core.models import Sdg
from apps.editions.exceptions import EditionSdgInUse
from apps.editions.models import Edition, EditionSdg
from apps.editions.rules import ensure_edition_not_closed
from apps.editions.selectors import list_edition_sdgs


@transaction.atomic
def set_edition_sdgs(*, actor: User, edition: Edition, sdg_ids: list[int]) -> list[Sdg]:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)

    links = EditionSdg.objects.filter(edition=edition)
    current = set(links.values_list("sdg_id", flat=True))
    requested = set(sdg_ids)
    additions = requested - current
    removals = current - requested

    if additions:
        active = set(
            Sdg.objects.select_for_update()
            .filter(pk__in=additions, active=True)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if additions != active:
            raise ValidationError(
                {"sdg_ids": "Somente ODS existentes e ativas podem ser incluídas."}
            )

    if removals:
        try:
            # O QuerySet de EditionSdg protege os vínculos usados por desafios.
            links.filter(sdg_id__in=removals).delete()
        except ValidationError as error:
            raise EditionSdgInUse() from error

    if additions:
        EditionSdg.objects.bulk_create(
            [EditionSdg(edition=edition, sdg_id=sdg_id) for sdg_id in sorted(additions)]
        )

    return list(list_edition_sdgs(edition.pk))
