"""UC07 — Atualiza uma etapa e configura seus campos de entrega (RF07)."""

from datetime import datetime
from decimal import Decimal
from typing import TypedDict, Unpack

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.exceptions import StageNotFound, translate_stage_position_conflict
from apps.editions.models import Edition, Stage, StageSubmissionField
from apps.editions.rules import (
    apply_stage_submission_field_values,
    ensure_formation_stage_is_unique,
    ensure_stage_edition_is_editable,
    ensure_stage_max_score_fits,
    ensure_stage_position_is_free,
    ensure_stage_scoring_can_change,
    ensure_stage_submission_fields_are_unused,
    ensure_stage_values_are_valid,
)


class _StageChanges(TypedDict, total=False):
    order: int
    name: str
    kind: str
    starts_at: datetime
    ends_at: datetime
    evaluation_ends_at: datetime | None
    scored: bool
    max_score: Decimal | None
    min_evaluations: int
    submission_fields: list[dict]


@transaction.atomic
def update_stage(
    *, actor: User, stage: Stage, **changes: Unpack[_StageChanges]
) -> Stage:
    ensure_actor_is_admin(actor)
    edition = Edition.objects.select_for_update().get(pk=stage.edition_id)
    ensure_stage_edition_is_editable(edition)
    try:
        stage = Stage.objects.select_for_update().get(pk=stage.pk, edition=edition)
    except Stage.DoesNotExist as error:
        raise StageNotFound() from error

    if set(changes) - _StageChanges.__annotations__.keys():
        raise ValidationError("Informe apenas propriedades editáveis da etapa.")
    previously_scored = stage.scored
    stage_changes = {
        key: value for key, value in changes.items() if key != "submission_fields"
    }
    for name, value in stage_changes.items():
        setattr(stage, name, value)
    ensure_stage_values_are_valid(stage)
    stage.name = stage.name.strip()
    ensure_stage_scoring_can_change(stage, previously_scored=previously_scored)
    ensure_formation_stage_is_unique(stage)
    ensure_stage_max_score_fits(stage)
    ensure_stage_position_is_free(stage)

    if "submission_fields" in changes:
        _replace_submission_fields(stage, changes["submission_fields"])
    # Mudar só os campos de entrega também atualiza a data da etapa.
    if changes:
        with translate_stage_position_conflict(), transaction.atomic():
            stage.save(update_fields=[*stage_changes, "updated_at"])
    return stage


def _replace_submission_fields(stage, payload):
    if not isinstance(payload, list):
        raise ValidationError({"submission_fields": "Informe uma lista de campos."})
    existing = {
        field.pk: field
        for field in stage.submission_fields.select_for_update().order_by("pk")
    }
    kept = set()
    changed_kinds = set()
    fields = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValidationError(
                {"submission_fields": "Informe objetos para os campos de entrega."}
            )
        if "id" in item:
            key = item["id"]
            if type(key) is not int or key not in existing or key in kept:
                raise ValidationError(
                    {"submission_fields": "ID repetido ou fora desta etapa."}
                )
            kept.add(key)
            field = existing[key]
            if "kind" in item and item["kind"] != field.kind:
                changed_kinds.add(key)
        else:
            field = StageSubmissionField(stage=stage)
        apply_stage_submission_field_values(
            field, {key: value for key, value in item.items() if key != "id"}
        )
        fields.append(field)

    removed = existing.keys() - kept
    if affected := removed | changed_kinds:
        ensure_stage_submission_fields_are_unused(affected)
    if removed:
        try:
            stage.submission_fields.filter(pk__in=removed).delete()
        except ProtectedError as error:
            raise ValidationError(
                {"submission_fields": "Campo com entrega não pode ser removido."}
            ) from error
    for field in fields:
        field.save()
