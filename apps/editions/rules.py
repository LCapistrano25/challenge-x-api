from django.apps import apps
from django.core.exceptions import ValidationError

from apps.editions.enums import EditionStatus
from apps.editions.exceptions import (
    EditionAlreadyExists,
    InvalidTeamLimits,
    TeamLimitsLocked,
)

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


def ensure_edition_identification_is_free(year: int, semester: int) -> None:
    """Impede duas edições com o mesmo ano e semestre (RN05)."""
    editions = apps.get_model("editions", "Edition").objects
    if editions.filter(year=year, semester=semester).exists():
        raise EditionAlreadyExists()


def ensure_team_limits_valid(min_members: int, max_members: int) -> None:
    """Exige mínimo e máximo maiores que zero e mínimo não maior que o máximo (RN07).

    O banco recusa o mesmo caso (edition_member_limits_valid); aqui sai o erro de
    negócio em vez de IntegrityError.
    """
    if min_members <= 0 or max_members <= 0 or min_members > max_members:
        raise InvalidTeamLimits()


def ensure_team_limits_editable(edition) -> None:
    """Só edição em configuração aceita mudar os limites (RF48, RN33).

    Edição publicada já divulgou o edital; encerrada não aceita alteração alguma.
    """
    if edition.status != EditionStatus.SETUP:
        raise TeamLimitsLocked()
