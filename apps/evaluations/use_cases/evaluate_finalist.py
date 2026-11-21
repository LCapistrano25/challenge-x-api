"""UC48 — Avaliador externo avalia o projeto finalista. RF42, RF43. Regras: RN33."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import ExternalReviewer, User
from apps.editions.rules import ensure_edition_not_closed
from apps.evaluations.enums import FinalEvaluationStatus
from apps.evaluations.exceptions import NotExternalReviewerActor
from apps.evaluations.models import FinalAnswer, FinalEvaluation, FinalForm
from apps.evaluations.rules import (
    ensure_all_questions_answered,
    ensure_final_evaluation_is_draft,
    ensure_final_form_published,
    ensure_reviewer_covers_finalist,
)
from apps.projects.models import Project


@transaction.atomic
def evaluate_finalist(
    *,
    actor: User,
    project: Project,
    answers: list[dict],
    comment: str = "",
    finalize: bool = False,
) -> FinalEvaluation:
    """Cria ou atualiza a avaliação final do avaliador e, se finalizar, a tranca.

    Cada resposta é {"question": FinalQuestion, "value", "text"}; as perguntas que
    ficarem fora da lista saem do rascunho. A nota daqui só serve à premiação: não
    entra na nota de 0 a 10 do projeto.

    Levanta NotExternalReviewerActor se o actor não for avaliador externo,
    FinalistNotFound se o projeto não for finalista da abrangência dele,
    EditionClosed, FinalFormNotPublished, FinalEvaluationAlreadyFinalized e
    ValidationError se a resposta não bater com a pergunta ou faltar pergunta
    ao finalizar.
    """
    question_ids = {data["question"].pk for data in answers}
    if len(question_ids) != len(answers):
        raise ValidationError({"answers": "Pergunta repetida."})

    reviewer = ExternalReviewer.objects.filter(user=actor).first()
    if actor.role != UserRole.EXTERNAL_REVIEWER or reviewer is None:
        raise NotExternalReviewerActor
    ensure_reviewer_covers_finalist(reviewer, project)
    ensure_edition_not_closed(project.edition)
    form = FinalForm.objects.filter(edition_id=project.edition_id).first()
    ensure_final_form_published(form)

    # Trava a avaliação: dois salvamentos ao mesmo tempo viram um depois do outro.
    evaluation, _ = FinalEvaluation.objects.select_for_update().get_or_create(
        project=project, reviewer=reviewer, defaults={"form": form}
    )
    ensure_final_evaluation_is_draft(evaluation)

    evaluation.comment = comment
    evaluation.save(update_fields=["comment", "updated_at"])
    for data in answers:
        answer = FinalAnswer.objects.filter(
            evaluation=evaluation, question=data["question"]
        ).first() or FinalAnswer(evaluation=evaluation, question=data["question"])
        answer.value = data.get("value")
        answer.text = data.get("text", "")
        answer.full_clean()
        answer.save()
    evaluation.answers.exclude(question__in=question_ids).delete()

    if finalize:
        ensure_all_questions_answered(evaluation)
        evaluation.status = FinalEvaluationStatus.EVALUATED
        evaluation.finalized_at = timezone.now()
        evaluation.full_clean()
        evaluation.save(update_fields=["status", "finalized_at", "updated_at"])
    return evaluation
