"""UC11 — Alterar a abrangência do avaliador externo na edição. RF11."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Edition, EditionReviewer
from apps.editions.rules import ensure_course_is_active, ensure_edition_not_closed


@transaction.atomic
def update_reviewer_scope(
    *, actor: User, link: EditionReviewer, course_id: int | None
) -> EditionReviewer:
    """Troca o curso que o avaliador avalia na edição; nulo = todos os cursos.

    Levanta NotAdminActor, EditionClosed ou ValidationError (curso inválido).
    """
    ensure_actor_is_admin(actor)

    edition = Edition.objects.select_for_update().get(pk=link.edition_id)
    ensure_edition_not_closed(edition)
    if course_id is not None:
        ensure_course_is_active(course_id)

    link.course_id = course_id
    link.save(update_fields=["course", "updated_at"])
    return link
