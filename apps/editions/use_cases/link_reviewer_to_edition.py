"""UC11 — Vincular avaliador externo à edição. RF11."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import ExternalReviewer, User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import ReviewerAlreadyLinked
from apps.editions.models import Edition, EditionReviewer
from apps.editions.rules import ensure_course_is_active, ensure_edition_not_closed


@transaction.atomic
def link_reviewer_to_edition(
    *, actor: User, edition: Edition, evaluator_id: int, course_id: int | None
) -> EditionReviewer:
    """Vincula o avaliador à edição; course_id nulo = todos os cursos.

    Levanta NotAdminActor, EditionClosed, ValidationError (avaliador ou curso
    inválido) ou ReviewerAlreadyLinked.
    """
    ensure_actor_is_admin(actor)

    # Trava a edição: o encerramento e outro vínculo simultâneo esperam este.
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_edition_not_closed(edition)

    if not ExternalReviewer.objects.filter(pk=evaluator_id).exists():
        raise ValidationError({"evaluator_id": "Avaliador externo não encontrado."})
    if course_id is not None:
        ensure_course_is_active(course_id)
    if EditionReviewer.objects.filter(
        edition=edition, reviewer_id=evaluator_id
    ).exists():
        raise ReviewerAlreadyLinked()

    return EditionReviewer.objects.create(
        edition=edition, reviewer_id=evaluator_id, course_id=course_id
    )
