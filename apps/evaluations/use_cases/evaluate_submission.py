"""UC43 — Professor avalia a entrega do projeto na etapa. RF37, RF38."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotTeacherActor
from apps.accounts.models import Teacher, User
from apps.editions.models import Stage
from apps.evaluations.enums import EvaluationStatus
from apps.evaluations.models import Evaluation, EvaluationItem
from apps.evaluations.rules import (
    ensure_all_criteria_scored,
    ensure_evaluation_is_draft,
    ensure_has_valid_submission,
    ensure_same_edition,
    ensure_stage_is_evaluable,
    ensure_submission_period_closed,
    ensure_teacher_in_challenge_course,
)
from apps.evaluations.use_cases.recalculate_stage_score import recalculate_stage_score
from apps.projects.models import Project


@transaction.atomic
def evaluate_submission(
    *,
    actor: User,
    project: Project,
    stage: Stage,
    items: list[dict],
    comment: str = "",
    finalize: bool = False,
) -> Evaluation:
    """Cria ou atualiza a avaliação do professor e, se finalizar, recalcula a nota.

    Cada item é {"stage_criterion", "points", "comment"}; os critérios que
    ficarem fora da lista saem do rascunho. Finalizar exige todos os critérios
    pontuados, o prazo de entrega da equipe encerrado e o de avaliação aberto, e
    torna a avaliação imutável.

    Levanta NotTeacherActor se o actor não for professor e ValidationError se
    ele não tiver vínculo com o curso do desafio, a etapa não for avaliável, o
    projeto não tiver entrega válida, a avaliação já estiver finalizada, os
    pontos passarem do máximo do critério ou faltar critério ao finalizar.
    """
    criteria_ids = {data["stage_criterion"].pk for data in items}
    if len(criteria_ids) != len(items):
        raise ValidationError({"items": "Critério repetido."})

    teacher = Teacher.objects.filter(user=actor).first()
    if actor.role != UserRole.TEACHER or teacher is None:
        raise NotTeacherActor()

    ensure_teacher_in_challenge_course(teacher, project)
    ensure_same_edition(project, stage.edition_id, "stage")
    ensure_stage_is_evaluable(stage)
    ensure_has_valid_submission(project, stage)

    # Trava a avaliação: dois salvamentos ao mesmo tempo viram um depois do outro.
    evaluation, _ = Evaluation.objects.select_for_update().get_or_create(
        project=project, stage=stage, teacher=teacher
    )
    ensure_evaluation_is_draft(evaluation)

    evaluation.comment = comment
    evaluation.save(update_fields=["comment", "updated_at"])

    for data in items:
        criterion = data["stage_criterion"]
        item = EvaluationItem.objects.filter(
            evaluation=evaluation, stage_criterion=criterion
        ).first() or EvaluationItem(evaluation=evaluation, stage_criterion=criterion)
        item.points = data["points"]
        item.comment = data.get("comment") or ""
        item.full_clean()
        item.save()
    evaluation.items.exclude(stage_criterion__in=criteria_ids).delete()

    if finalize:
        ensure_submission_period_closed(project, stage)
        ensure_all_criteria_scored(evaluation)
        evaluation.status = EvaluationStatus.FINALIZED
        evaluation.finalized_at = timezone.now()
        # O clean() do model confere o prazo de avaliação da etapa.
        evaluation.full_clean()
        evaluation.save(update_fields=["status", "finalized_at", "updated_at"])
        recalculate_stage_score(project=project, stage=stage)
    return evaluation
