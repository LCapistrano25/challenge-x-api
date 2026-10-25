from django.apps import apps
from django.core.exceptions import ValidationError

# Os models importam estas regras; por isso elas pegam os models pelo registro
# do Django (como a FK por string), sem import que fecharia o ciclo.


def ensure_sdg_enabled_in_edition(edition_id: int, sdg_id: int) -> None:
    """Exige que a ODS esteja entre as aceitas na edição (RN09)."""
    edition_sdgs = apps.get_model("editions", "EditionSdg").objects
    if not edition_sdgs.filter(edition_id=edition_id, sdg_id=sdg_id).exists():
        raise ValidationError({"sdg": "A ODS não está habilitada nesta edição."})


def ensure_sdg_not_used_by_challenges(edition_id: int, sdg_id: int) -> None:
    """Impede tirar da edição uma ODS que algum desafio usa (RN09)."""
    challenges = apps.get_model("editions", "Challenge").objects
    if challenges.filter(edition_id=edition_id, sdg_id=sdg_id).exists():
        raise ValidationError("Há desafios desta edição usando esta ODS.")


def ensure_criterion_in_stage_edition(stage, criterion) -> None:
    """Exige que critério e etapa sejam da mesma edição (RF08)."""
    if stage.edition_id != criterion.edition_id:
        raise ValidationError("O critério pertence a outra edição.")
