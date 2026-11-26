"""UC07 — Cadastra uma etapa e seus campos de entrega (RF07)."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import translate_stage_position_conflict
from apps.editions.models import Edition, Stage, StageSubmissionField
from apps.editions.rules import (
    apply_stage_submission_field_values,
    ensure_formation_stage_is_unique,
    ensure_stage_edition_is_editable,
    ensure_stage_max_score_fits,
    ensure_stage_position_is_free,
    ensure_stage_values_are_valid,
)


@transaction.atomic
def create_stage(
    *,
    actor: User,
    edition: Edition,
    order: int,
    name: str,
    kind: str,
    starts_at: datetime,
    ends_at: datetime,
    evaluation_ends_at: datetime | None = None,
    scored: bool = True,
    max_score: Decimal | None = None,
    min_evaluations: int = 1,
    submission_fields: Sequence[dict] = (),
) -> Stage:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=edition.pk)
    ensure_stage_edition_is_editable(edition)
    stage = Stage(
        edition=edition,
        order=order,
        name=name,
        kind=kind,
        starts_at=starts_at,
        ends_at=ends_at,
        evaluation_ends_at=evaluation_ends_at,
        scored=scored,
        max_score=max_score,
        min_evaluations=min_evaluations,
    )
    ensure_stage_values_are_valid(stage)
    stage.name = stage.name.strip()
    ensure_formation_stage_is_unique(stage)
    ensure_stage_max_score_fits(stage)
    ensure_stage_position_is_free(stage)

    if not isinstance(submission_fields, (list, tuple)):
        raise ValidationError({"submission_fields": "Informe uma lista de campos."})
    fields = []
    for data in submission_fields:
        field = StageSubmissionField(stage=stage)
        apply_stage_submission_field_values(field, data)
        fields.append(field)

    with translate_stage_position_conflict(), transaction.atomic():
        stage.save()
    StageSubmissionField.objects.bulk_create(fields)
    return stage
