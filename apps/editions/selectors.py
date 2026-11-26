from django.db.models import Prefetch, QuerySet

from apps.core.models import Sdg
from apps.editions.exceptions import CategoryNotFound, CriterionNotFound
from apps.editions.models import (
    Category,
    Challenge,
    Criterion,
    Edition,
    EditionReviewer,
    Stage,
    StageCriterion,
    StageSubmissionField,
)


def get_locked_criterion(criterion_id: int) -> Criterion:
    try:
        return Criterion.objects.select_for_update().get(pk=criterion_id)
    except Criterion.DoesNotExist as error:
        raise CriterionNotFound() from error


def stages_with_submission_fields():
    return Stage.objects.prefetch_related(
        Prefetch(
            "submission_fields",
            queryset=StageSubmissionField.objects.order_by("pk"),
        )
    )


def list_edition_stages(edition_id: int) -> QuerySet[Stage]:
    return (
        stages_with_submission_fields().filter(edition_id=edition_id).order_by("order")
    )


def list_stage_criteria(stage_id: int) -> QuerySet[StageCriterion]:
    """Matriz de avaliação da etapa (RF08)."""
    return (
        StageCriterion.objects.filter(stage_id=stage_id)
        .select_related("criterion")
        .order_by("criterion_id")
    )


def list_edition_criteria(edition_id: int) -> QuerySet[Criterion]:
    return Criterion.objects.filter(edition_id=edition_id).order_by("id")


def list_edition_categories(edition_id: int) -> QuerySet[Category]:
    """Lista as categorias cadastradas na edição (RF49)."""
    return Category.objects.filter(edition_id=edition_id).order_by("id")


def get_locked_category(category_id: int) -> Category:
    """Busca a categoria após a trava da edição, dentro da transação."""
    try:
        return Category.objects.select_for_update().get(pk=category_id)
    except Category.DoesNotExist as error:
        raise CategoryNotFound() from error


def list_edition_reviewers(edition_id: int) -> QuerySet[EditionReviewer]:
    """Vínculos de avaliador externo de uma edição (RF11)."""
    # O serializer lê usuário e curso de cada vínculo: busca tudo numa consulta.
    return (
        EditionReviewer.objects.filter(edition_id=edition_id)
        .select_related("reviewer__user", "course")
        .order_by("id")
    )


def list_editions():
    """Todas as edições, na ordem do model (ano e semestre, da mais recente)."""
    return Edition.objects.all()


def list_edition_sdgs(edition_id: int) -> QuerySet[Sdg]:
    """Lista as ODS habilitadas, incluindo as inativadas no catálogo."""
    return Sdg.objects.filter(edition_links__edition_id=edition_id).order_by("number")


def list_edition_challenges(
    *,
    edition_id: int,
    course_id: int | None = None,
    sdg_id: int | None = None,
    active: bool | None = None,
) -> QuerySet[Challenge]:
    filters = {"course_id": course_id, "sdg_id": sdg_id, "active": active}
    return (
        Challenge.objects.filter(
            edition_id=edition_id,
            **{field: value for field, value in filters.items() if value is not None},
        )
        .select_related("course", "sdg")
        .order_by("id")
    )
