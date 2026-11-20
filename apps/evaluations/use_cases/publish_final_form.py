"""UC12 — Publicar o formulário da etapa final. RF12. Regras: RN33."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.rules import ensure_edition_not_closed
from apps.evaluations.models import FinalForm
from apps.evaluations.rules import ensure_final_form_publishable


@transaction.atomic
def publish_final_form(*, actor: User, form: FinalForm) -> FinalForm:
    """Publica o formulário, liberando a etapa final para lançamentos.

    Levanta NotAdminActor se o actor não for admin, EditionClosed se a edição
    estiver encerrada, FinalFormAlreadyPublished se já estiver publicado e
    FinalFormEmpty se não tiver perguntas.
    """
    ensure_actor_is_admin(actor)
    form = (
        FinalForm.objects.select_for_update().select_related("edition").get(pk=form.pk)
    )
    ensure_edition_not_closed(form.edition)
    ensure_final_form_publishable(form)

    form.published = True
    form.save(update_fields=["published", "updated_at"])
    return form
