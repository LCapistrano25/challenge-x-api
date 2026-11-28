from datetime import datetime
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import Sum, Value
from django.db.models.functions import Lower
from django.utils import timezone

from apps.editions.enums import EditionStatus, FieldKind, StageKind
from apps.editions.exceptions import (
    CriterionInUseByEvaluations,
    CriterionNameTaken,
    EditionAlreadyExists,
    EditionClosed,
    EditionNotInSetup,
    EditionPublished,
    InvalidTeamLimits,
    PublicationRequirementsNotMet,
    StagePositionTaken,
    TeamLimitsLocked,
    TiebreakOrderTaken,
)

# Os models importam estas regras; por isso elas pegam os models pelo registro
# do Django (como a FK por string), sem import que fecharia o ciclo.


def ensure_sdg_enabled_in_edition(
    edition_id: int, sdg_id: int, *, error_field: str = "sdg"
) -> None:
    """Exige que a ODS esteja entre as aceitas na edição (RN09)."""
    edition_sdgs = apps.get_model("editions", "EditionSdg").objects
    if not edition_sdgs.filter(edition_id=edition_id, sdg_id=sdg_id).exists():
        raise ValidationError({error_field: "A ODS não está habilitada nesta edição."})


def ensure_challenge_sdg_is_valid(edition_id: int, sdg_id: int) -> None:
    """Exige ODS ativa e habilitada no cadastro ou na troca de vínculo (RF05)."""
    if (
        not apps.get_model("core", "Sdg")
        .objects.filter(pk=sdg_id, active=True)
        .exists()
    ):
        raise ValidationError({"sdg_id": "A ODS deve existir e estar ativa."})
    ensure_sdg_enabled_in_edition(edition_id, sdg_id, error_field="sdg_id")


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

    stages = list(edition.stages.filter(scored=True))
    if sum(stage.max_score for stage in stages) != MAX_FINAL_SCORE:
        pending["stages"] = "As etapas pontuadas devem somar 10,00 pontos."
    # Os critérios não somam o valor da etapa: cada um vale 10 por padrão e
    # funciona como peso (D-02). Só precisa haver critério em cada etapa pontuada.
    if any(not stage.criterion_links.exists() for stage in stages):
        pending["stage_criteria"] = "Vincule critérios a cada etapa pontuada."
    # Sem professores suficientes a nota fica pendente e trava os finalistas (#304).
    needed = max((stage.min_evaluations for stage in stages), default=0)
    if needed:
        links = apps.get_model("accounts", "TeacherCourse").objects.filter(
            active=True, teacher__user__is_active=True
        )
        courses = (
            edition.challenges.filter(active=True, course__active=True)
            .values_list("course_id", "course__name")
            .distinct()
        )
        short = sorted(
            name
            for course_id, name in courses
            if links.filter(course_id=course_id).count() < needed
        )
        if short:
            pending["teachers"] = (
                f"Vincule ao menos {needed} professor(es) ativo(s) a cada curso com "
                f"desafio: {', '.join(short)}."
            )

    if pending:
        raise PublicationRequirementsNotMet(pending)


def ensure_criterion_values_are_valid(*, name: str, tiebreak_order: int | None) -> None:
    errors = {}
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 150:
        errors["name"] = "Informe um nome de 1 a 150 caracteres."
    if tiebreak_order is not None and (
        type(tiebreak_order) is not int or not 1 <= tiebreak_order <= 32767
    ):
        errors["tiebreak_order"] = "Informe uma ordem de desempate de 1 a 32767."
    if errors:
        raise ValidationError(errors)


def ensure_criterion_values_are_unique(
    *,
    edition_id: int,
    name: str,
    tiebreak_order: int | None,
    criterion_id: int | None = None,
) -> None:
    """Confere nome e posição de desempate no escopo da edição."""
    criteria = apps.get_model("editions", "Criterion").objects.filter(
        edition_id=edition_id
    )
    if criterion_id is not None:
        criteria = criteria.exclude(pk=criterion_id)
    if (
        criteria.alias(normalized_name=Lower("name"))
        .filter(normalized_name=Lower(Value(name)))
        .exists()
    ):
        raise CriterionNameTaken()
    if (
        tiebreak_order is not None
        and criteria.filter(tiebreak_order=tiebreak_order).exists()
    ):
        raise TiebreakOrderTaken()


def ensure_criterion_has_no_evaluations(criterion_id: int) -> None:
    """Bloqueia a alteração se uma etapa vinculada já tiver avaliações."""
    evaluations = apps.get_model("evaluations", "Evaluation").objects
    if evaluations.filter(stage__criterion_links__criterion_id=criterion_id).exists():
        raise CriterionInUseByEvaluations()


def ensure_criterion_can_be_saved(
    *, criterion_id: int | None, edition_id: int | None
) -> None:
    """Valida a edição de origem e a de destino no formulário do critério."""
    criteria = apps.get_model("editions", "Criterion").objects
    edition_ids = {edition_id}
    if criterion_id is not None:
        previous_edition_id = (
            criteria.filter(pk=criterion_id)
            .values_list("edition_id", flat=True)
            .first()
        )
        edition_ids.add(previous_edition_id)
    editions = apps.get_model("editions", "Edition").objects.filter(pk__in=edition_ids)
    for edition in editions:
        ensure_edition_not_closed(edition)
    if criterion_id is not None:
        ensure_criterion_has_no_evaluations(criterion_id)


def ensure_stage_edition_is_editable(edition) -> None:
    """A API de configuração aceita escrita só antes da publicação."""
    ensure_edition_not_closed(edition)
    if edition.status == EditionStatus.PUBLISHED:
        raise EditionPublished()


def ensure_stage_values_are_valid(stage) -> None:
    """Valida o estado final da etapa (UC07, RF07)."""
    errors = {}
    for field in ("order", "min_evaluations"):
        value = getattr(stage, field)
        if type(value) is not int or not 1 <= value <= 32767:
            errors[field] = "Informe um inteiro entre 1 e 32767."
    if not isinstance(stage.name, str) or not 1 <= len(stage.name.strip()) <= 100:
        errors["name"] = "Informe um nome de 1 a 100 caracteres."
    if stage.kind not in StageKind.values:
        errors["kind"] = "Informe um tipo de etapa válido."
    if type(stage.scored) is not bool:
        errors["scored"] = "Informe se a etapa é pontuada."
    elif stage.scored and stage.kind in (StageKind.FINAL, StageKind.FORMATION):
        errors["scored"] = "Etapas de formação e finais não podem ser pontuadas."

    score = stage.max_score
    if stage.scored is True:
        if (
            not isinstance(score, Decimal)
            or not score.is_finite()
            or score.as_tuple().exponent < -2
            or not 0 < score <= MAX_FINAL_SCORE
        ):
            errors["max_score"] = (
                "Informe uma pontuação positiva de até 10, com até duas casas decimais."
            )
    elif stage.scored is False and score is not None:
        errors["max_score"] = "Etapa não pontuada deve ter pontuação nula."

    for field in ("starts_at", "ends_at", "evaluation_ends_at"):
        value = getattr(stage, field)
        if field == "evaluation_ends_at" and value is None and stage.scored is not True:
            continue
        if not isinstance(value, datetime) or timezone.is_naive(value):
            errors[field] = "Informe uma data e hora com fuso."
    if (
        not {"starts_at", "ends_at"} & errors.keys()
        and stage.ends_at <= stage.starts_at
    ):
        errors["ends_at"] = "O fim das entregas deve ser posterior ao início."
    if (
        not {"ends_at", "evaluation_ends_at"} & errors.keys()
        and stage.evaluation_ends_at is not None
        and stage.evaluation_ends_at <= stage.ends_at
    ):
        errors["evaluation_ends_at"] = (
            "O prazo de avaliação deve ser posterior ao fim das entregas."
        )
    if errors:
        raise ValidationError(errors)


def ensure_stage_position_is_free(stage) -> None:
    stages = apps.get_model("editions", "Stage").objects
    if (
        stages.filter(edition_id=stage.edition_id, order=stage.order)
        .exclude(pk=stage.pk)
        .exists()
    ):
        raise StagePositionTaken()


def ensure_formation_stage_is_unique(stage) -> None:
    """Confere a etapa de formação com a edição já travada pelo chamador."""
    if stage.kind != StageKind.FORMATION:
        return
    stages = apps.get_model("editions", "Stage").objects
    if (
        stages.filter(edition_id=stage.edition_id, kind=StageKind.FORMATION)
        .exclude(pk=stage.pk)
        .exists()
    ):
        raise ValidationError({"kind": "Já existe uma etapa de formação nesta edição."})


def ensure_stage_submission_field_is_valid(field) -> None:
    max_size = field.max_size_mb
    if (
        field.kind not in FieldKind.values
        or not isinstance(field.label, str)
        or len(field.label) > 150
        or type(field.required) is not bool
        or not isinstance(field.formats, str)
        or len(field.formats) > 200
    ):
        raise ValidationError(
            {"submission_fields": "Informe campos de entrega válidos."}
        )
    if max_size is not None and (
        type(max_size) is not int or not 1 <= max_size <= 32767
    ):
        raise ValidationError(
            {"submission_fields": "O tamanho deve estar entre 1 e 32767 MB."}
        )
    if field.kind != FieldKind.FILE and (field.formats or max_size is not None):
        raise ValidationError(
            {"submission_fields": "Formato e tamanho só se aplicam a arquivos."}
        )


def apply_stage_submission_field_values(field, data) -> None:
    """Valida e aplica somente os campos informados no estado em memória."""
    if (
        not isinstance(data, dict)
        or "kind" not in data
        or set(data)
        - {
            "kind",
            "label",
            "required",
            "formats",
            "max_size_mb",
        }
    ):
        raise ValidationError(
            {"submission_fields": "Informe campos de entrega válidos."}
        )
    for name, value in data.items():
        setattr(field, name, "" if name == "formats" and value is None else value)
    ensure_stage_submission_field_is_valid(field)


def ensure_stage_submission_fields_are_unused(field_ids) -> None:
    if (
        apps.get_model("projects", "SubmissionItem")
        .objects.filter(field_id__in=field_ids)
        .exists()
    ):
        raise ValidationError(
            {"submission_fields": "Campo com entrega: preserve o campo e seu tipo."}
        )


def ensure_stage_scoring_can_change(stage, *, previously_scored: bool) -> None:
    if previously_scored and not stage.scored and stage.criterion_links.exists():
        raise ValidationError(
            {"scored": "Remova os critérios vinculados antes de desativar a pontuação."}
        )
