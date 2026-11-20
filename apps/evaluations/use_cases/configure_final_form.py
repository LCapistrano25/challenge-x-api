"""UC12 — Estruturar o formulário da etapa final. RF12. Regras: RN33."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
from apps.editions.models import Edition
from apps.evaluations.models import FinalForm, FinalQuestion
from apps.evaluations.rules import ensure_final_form_editable


@transaction.atomic
def configure_final_form(
    *, actor: User, edition: Edition, title: str, questions: list[dict]
) -> FinalForm:
    """Cria ou substitui o título e o conjunto de perguntas do formulário da edição.

    Cada pergunta é um dict com order, prompt, kind e max_score.

    Levanta NotAdminActor se o actor não for admin, EditionClosed se a edição
    estiver encerrada e FinalFormHasAnswers se o formulário publicado já tiver
    respostas.
    """
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    if edition.status == EditionStatus.CLOSED:
        raise EditionClosed

    form, _ = FinalForm.objects.select_for_update().get_or_create(edition=edition)
    ensure_final_form_editable(form)

    form.title = title or ""
    form.save(update_fields=["title", "updated_at"])
    # Substituição completa: as perguntas só têm resposta em formulário publicado,
    # e esse caso já foi barrado acima.
    form.questions.all().delete()
    FinalQuestion.objects.bulk_create(FinalQuestion(form=form, **q) for q in questions)
    return form
