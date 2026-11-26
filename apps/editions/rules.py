from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import Sum

from apps.editions.enums import EditionStatus
from apps.editions.exceptions import (
    EditionAlreadyExists,
    EditionClosed,
    EditionNotInSetup,
    EditionPublished,
    InvalidTeamLimits,
    PublicationRequirementsNotMet,
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


MAX_FINAL_SCORE = Decimal("10")


def ensure_stage_max_score_fits(stage) -> None:
    """As etapas pontuadas somam no máximo 10 (INT-01).

    A igualdade (somar exatamente 10) só vale ao publicar a edição. Os critérios
    não somam o valor da etapa: cada um vale 10 por padrão e funciona como peso
    (D-02).
    """
    if not stage.scored or stage.max_score is None:
        return
    stages = apps.get_model("editions", "Stage").objects
    others = (
        stages.filter(edition_id=stage.edition_id, scored=True)
        .exclude(pk=stage.pk)
        .aggregate(total=Sum("max_score"))["total"]
        or 0
    )
    if others + stage.max_score > MAX_FINAL_SCORE:
        raise ValidationError(
            {"max_score": "As etapas pontuadas da edição passariam de 10 pontos."}
        )


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
    if edition.status == EditionStatus.PUBLISHED:
        raise EditionPublished()
    if edition.status != EditionStatus.SETUP:
        raise TeamLimitsLocked()


def ensure_edition_not_closed(edition) -> None:
    """Edição encerrada não aceita alteração (RF11: o vínculo expira com ela)."""
    if edition.status == EditionStatus.CLOSED:
        raise EditionClosed()


def ensure_course_is_active(course_id: int) -> None:
    """Exige curso existente e ativo para a abrangência do avaliador (RF11)."""
    courses = apps.get_model("core", "Course").objects
    if not courses.filter(pk=course_id, active=True).exists():
        raise ValidationError({"course_id": "Curso inválido."})


def ensure_edition_ready_for_publication(edition) -> None:
    """Exige a configuração mínima da edição (RF09, INT-01, INT-02)."""
    if edition.status != EditionStatus.SETUP:
        raise EditionNotInSetup()

    pending = {}
    if not apps.get_model("core", "Course").objects.filter(active=True).exists():
        pending["courses"] = "Cadastre pelo menos um curso ativo."
    enabled_sdgs = edition.sdg_links.filter(sdg__active=True).values("sdg_id")
    if not enabled_sdgs.exists():
        pending["sdgs"] = "Habilite pelo menos uma ODS ativa na edição."
    if not edition.challenges.filter(
        active=True, course__active=True, sdg_id__in=enabled_sdgs
    ).exists():
        pending["challenges"] = "Cadastre um desafio ativo para curso e ODS ativos."
    if not edition.categories.exists():
        pending["categories"] = "Cadastre pelo menos uma categoria."
    if not edition.criteria.exists():
        pending["criteria"] = "Cadastre pelo menos um critério."
    try:
        ensure_team_limits_valid(edition.min_members, edition.max_members)
    except InvalidTeamLimits:
        pending["team_limits"] = str(InvalidTeamLimits())

    stages = list(
        edition.stages.filter(scored=True).annotate(
            criteria_total=Sum("criterion_links__max_score")
        )
    )
    if sum(stage.max_score for stage in stages) != MAX_FINAL_SCORE:
        pending["stages"] = "As etapas pontuadas devem somar 10,00 pontos."
    if any(stage.criteria_total != stage.max_score for stage in stages):
        pending["stage_criteria"] = (
            "Os critérios de cada etapa devem somar o valor dela."
        )

    if pending:
        raise PublicationRequirementsNotMet(pending)
