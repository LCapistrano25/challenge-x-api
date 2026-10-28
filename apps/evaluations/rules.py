from django.apps import apps
from django.core.exceptions import ValidationError

from apps.evaluations.enums import QuestionKind

# Os models importam estas regras; por isso elas pegam os models pelo registro
# do Django (como a FK por string), sem import que fecharia o ciclo.


def ensure_same_edition(project, edition_id: int, field: str) -> None:
    """A etapa ou o formulário pertencem à edição do projeto."""
    if project.edition_id != edition_id:
        raise ValidationError({field: "Não é da edição do projeto."})


def ensure_item_within_criterion(item) -> None:
    """Critério da etapa avaliada e pontos entre 0 e o máximo do critério (RF38)."""
    if item.stage_criterion.stage_id != item.evaluation.stage_id:
        raise ValidationError({"stage_criterion": "O critério é de outra etapa."})
    if item.points is not None and item.points > item.stage_criterion.max_score:
        raise ValidationError(
            {"points": f"Máximo do critério: {item.stage_criterion.max_score}."}
        )


def ensure_rectification_within_criterion(rectification) -> None:
    """A nota retificada também respeita o máximo do critério (RF14)."""
    max_score = rectification.item.stage_criterion.max_score
    if rectification.new_points > max_score:
        raise ValidationError({"new_points": f"Máximo do critério: {max_score}."})


def ensure_within_evaluation_deadline(evaluation) -> None:
    """O professor finaliza até o prazo de avaliação da etapa (RF38, P-19).

    A retificação do admin (RF14) não passa por aqui: ela muda o item, não a
    avaliação.
    """
    deadline = evaluation.stage.evaluation_ends_at
    if evaluation.finalized_at and deadline and evaluation.finalized_at > deadline:
        raise ValidationError(
            {"finalized_at": "O prazo de avaliação da etapa já terminou."}
        )


def ensure_reviewer_in_edition(evaluation) -> None:
    """Só avalia quem foi convidado para a edição do projeto (RF11, RF43)."""
    reviewers = apps.get_model("editions", "EditionReviewer").objects
    if not reviewers.filter(
        edition_id=evaluation.project.edition_id, reviewer_id=evaluation.reviewer_id
    ).exists():
        raise ValidationError({"reviewer": "O avaliador não está nesta edição."})


def ensure_answer_matches_question(answer) -> None:
    """Pergunta do mesmo formulário; nota só em SCORE, texto nos demais (RF43)."""
    question = answer.question
    if question.form_id != answer.evaluation.form_id:
        raise ValidationError({"question": "A pergunta é de outro formulário."})
    if question.kind == QuestionKind.SCORE:
        if answer.value is None or answer.text:
            raise ValidationError({"value": "Pergunta de nota exige só o valor."})
        if not 0 <= answer.value <= question.max_score:
            raise ValidationError({"value": f"Entre 0 e {question.max_score}."})
    elif answer.value is not None or not answer.text:
        raise ValidationError(
            {"text": "Pergunta de texto ou conceito exige só o texto."}
        )
