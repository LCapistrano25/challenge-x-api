"""UC08 — Define os critérios e as pontuações máximas da etapa (RF08)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import StageNotFound
from apps.editions.models import Criterion, Edition, Stage, StageCriterion
from apps.editions.rules import ensure_stage_edition_is_editable
from apps.editions.selectors import list_stage_criteria

# StageCriterion.max_score é decimal(4, 2).
MAX_CRITERION_SCORE = Decimal("99.99")


@transaction.atomic
def configure_stage_criteria(
    *, actor: User, stage: Stage, items: list[dict]
) -> list[StageCriterion]:
    """Substitui o conjunto de critérios da etapa pontuada.

    Cada critério vale 10 por padrão e funciona como peso: a soma não precisa
    igualar o valor da etapa (D-02). Critério que sai é desvinculado; o que fica
    mantém o vínculo e muda só a pontuação.

    Levanta NotAdminActor, EditionClosed, EditionPublished, StageNotFound e
    ValidationError (etapa não pontuada, critério repetido, de outra edição ou
    pontuação fora de 0 < max_score <= 99,99).
    """
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=stage.edition_id)
    ensure_stage_edition_is_editable(edition)
    try:
        stage = Stage.objects.select_for_update().get(pk=stage.pk, edition=edition)
    except Stage.DoesNotExist as error:
        raise StageNotFound() from error

    if not stage.scored:
        raise ValidationError({"items": "Somente etapas pontuadas têm critérios."})
    scores = {}
    for item in items:
        criterion_id, max_score = item["criterion_id"], item["max_score"]
        if criterion_id in scores:
            raise ValidationError({"items": "Há critério repetido na lista."})
        if not Decimal(0) < max_score <= MAX_CRITERION_SCORE:
            raise ValidationError(
                {"items": "A pontuação máxima deve ser maior que 0 e até 99,99."}
            )
        scores[criterion_id] = max_score
    found = set(
        Criterion.objects.filter(pk__in=scores, edition=edition).values_list(
            "pk", flat=True
        )
    )
    if found != set(scores):
        raise ValidationError({"items": "Há critério que não é desta edição."})

    StageCriterion.objects.filter(stage=stage).exclude(criterion_id__in=scores).delete()
    for criterion_id, max_score in scores.items():
        StageCriterion.objects.update_or_create(
            stage=stage, criterion_id=criterion_id, defaults={"max_score": max_score}
        )
    return list(list_stage_criteria(stage.pk))
