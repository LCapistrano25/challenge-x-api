"""UC12 — Estruturar o formulário da etapa final. RF12. Regras: RN33."""

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Edition
from apps.editions.rules import ensure_edition_not_closed
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
    ensure_edition_not_closed(edition)

    form, _ = FinalForm.objects.select_for_update().get_or_create(edition=edition)
    ensure_final_form_editable(form)

    form.title = title or ""
    form.save(update_fields=["title", "updated_at"])
    # Atualiza pela ordem e mantém o id: o avaliador pode estar com o formulário
    # aberto, e o envio dele referencia as perguntas por id.
    existing = {q.order: q for q in form.questions.all()}
    for data in questions:
        question = existing.pop(data["order"], None) or FinalQuestion(form=form)
        for field, value in data.items():
            setattr(question, field, value)
        question.save()
    FinalQuestion.objects.filter(pk__in=[q.pk for q in existing.values()]).delete()
    return form
