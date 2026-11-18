from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.editions.enums import StageKind
from apps.evaluations.enums import EvaluationStatus, QuestionKind
from apps.evaluations.exceptions import TeacherNotInCourse

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


def ensure_teacher_in_challenge_course(teacher, project) -> None:
    """Só avalia o professor com vínculo ativo no curso do desafio (RF38, RN04)."""
    course_id = project.challenge.course_id if project.challenge_id else None
    if not teacher.course_links.filter(course_id=course_id, active=True).exists():
        raise TeacherNotInCourse()


def ensure_stage_is_evaluable(stage) -> None:
    """Só etapas pontuadas de entrega têm avaliação do professor (RF38)."""
    if stage.kind != StageKind.SUBMISSION or not stage.scored:
        raise ValidationError({"stage": "A etapa não tem avaliação do professor."})


def ensure_has_valid_submission(project, stage) -> None:
    """A avaliação incide sobre a versão válida da entrega (RF38)."""
    # Import tardio: os models de evaluations importam este módulo.
    from apps.projects.selectors import get_valid_version

    submission = project.submissions.filter(stage=stage).first()
    if submission is None or get_valid_version(submission) is None:
        raise ValidationError({"submission": "O projeto não tem entrega válida."})


def ensure_submission_period_closed(project, stage) -> None:
    """Só finaliza depois do prazo da equipe, com a prorrogação se houver (RF38).

    Antes disso a equipe ainda pode enviar uma versão que invalidaria a nota.
    """
    from apps.projects.selectors import get_submission_deadline

    if timezone.now() <= get_submission_deadline(project, stage):
        raise ValidationError(
            {"stage": "O prazo de entrega da equipe ainda está aberto."}
        )


def ensure_evaluation_is_draft(evaluation) -> None:
    """Avaliação finalizada é imutável; só a retificação do admin muda (RF14)."""
    if evaluation.status == EvaluationStatus.FINALIZED:
        raise ValidationError({"status": "A avaliação já foi finalizada."})


def ensure_all_criteria_scored(evaluation) -> None:
    """Finalizar exige pontos em todos os critérios da etapa (RF38)."""
    scored = evaluation.items.values_list("stage_criterion_id", flat=True)
    criteria = evaluation.stage.criterion_links
    if not criteria.exists() or criteria.exclude(pk__in=scored).exists():
        raise ValidationError({"items": "Pontue todos os critérios da etapa."})
