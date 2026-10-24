from django.core.exceptions import ValidationError

from apps.editions.models.edition import EditionSdg


def ensure_sdg_enabled_in_edition(edition_id: int, sdg_id: int) -> None:
    """Exige que a ODS esteja entre as aceitas na edição (RN09)."""
    if not EditionSdg.objects.filter(edition_id=edition_id, sdg_id=sdg_id).exists():
        raise ValidationError({"sdg": "A ODS não está habilitada nesta edição."})


def ensure_sdg_not_used_by_challenges(edition_id: int, sdg_id: int) -> None:
    """Impede tirar da edição uma ODS que algum desafio usa (RN09)."""
    from apps.editions.models.challenge import Challenge  # challenge importa rules

    if Challenge.objects.filter(edition_id=edition_id, sdg_id=sdg_id).exists():
        raise ValidationError("Há desafios desta edição usando esta ODS.")


def ensure_criterion_in_stage_edition(stage, criterion) -> None:
    """Exige que critério e etapa sejam da mesma edição (RF08)."""
    if stage.edition_id != criterion.edition_id:
        raise ValidationError("O critério pertence a outra edição.")
