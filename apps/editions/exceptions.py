from contextlib import contextmanager
from http import HTTPStatus

from django.db import IntegrityError

from apps.core.exceptions import BusinessRuleViolation, ExternalServiceError


class EditionError(BusinessRuleViolation):
    """Base das violações de regra de negócio do app editions."""

    code = "edition_error"
    default_message = "Operação não permitida para a edição."


class EditionAlreadyExists(EditionError):
    code = "edition_exists"
    default_message = "Já existe edição para este ano e semestre."


class TeamLimitsLocked(EditionError):
    code = "team_limits_locked"
    default_message = "Os limites da equipe não podem ser alterados nesta edição."


class EditionPublished(TeamLimitsLocked):
    code = "edition_published"
    default_message = "A configuração está congelada após a publicação do edital."


class InvalidTeamLimits(EditionError):
    code = "validation_error"
    default_message = (
        "Os limites devem ser maiores que zero e o mínimo não pode passar do máximo."
    )
    http_status = HTTPStatus.BAD_REQUEST


class EditionClosed(EditionError):
    code = "edition_closed"
    default_message = "A edição está encerrada e não pode ser alterada."


class CriterionInUseByEvaluations(EditionError):
    code = "criterion_in_use_by_evaluations"
    default_message = "Há avaliações iniciadas em etapa que usa o critério."


class CriterionNotFound(EditionError):
    code = "not_found"
    default_message = "Critério não encontrado."
    http_status = HTTPStatus.NOT_FOUND


class CriterionLinkedToStage(EditionError):
    code = "criterion_linked_to_stage"
    default_message = "O critério está vinculado a uma etapa."


class CriterionNameTaken(EditionError):
    code = "criterion_name_taken"
    default_message = "Já existe critério com este nome na edição."


class TiebreakOrderTaken(EditionError):
    code = "tiebreak_order_taken"
    default_message = "Já existe critério nesta posição de desempate."


@contextmanager
def translate_criterion_conflict():
    """Traduz as violações das duas restrições de unicidade do critério."""
    try:
        yield
    except IntegrityError as error:
        diagnostics = getattr(error.__cause__, "diag", None)
        match getattr(diagnostics, "constraint_name", None):
            case "unique_criterion_name_per_edition":
                raise CriterionNameTaken() from error
            case "unique_tiebreak_order_per_edition":
                raise TiebreakOrderTaken() from error
        raise


class CategoryNameTaken(EditionError):
    code = "category_name_taken"
    default_message = "Já existe categoria com este nome na edição."


class CategoryInUse(EditionError):
    code = "category_in_use"
    default_message = "A categoria é usada por projetos e só pode ser desativada."


class CategoryNotFound(EditionError):
    code = "not_found"
    default_message = "Categoria não encontrada."
    http_status = HTTPStatus.NOT_FOUND


@contextmanager
def translate_category_name_conflict():
    """Traduz somente a violação da unicidade do nome na edição."""
    try:
        yield
    except IntegrityError as error:
        diagnostics = getattr(error.__cause__, "diag", None)
        if getattr(diagnostics, "constraint_name", None) == (
            "unique_category_name_per_edition"
        ):
            raise CategoryNameTaken() from error
        raise


class EditionSdgInUse(EditionError):
    code = "sdg_in_use"
    default_message = "A ODS está vinculada a desafios da edição."


class ReviewerAlreadyLinked(EditionError):
    code = "evaluator_already_linked"
    default_message = "O avaliador já está vinculado a esta edição."


class EditionNotInSetup(EditionError):
    code = "edition_not_in_setup"
    default_message = "Somente edições em configuração podem ser publicadas."


class PublicationRequirementsNotMet(EditionError):
    code = "publication_requirements_not_met"
    default_message = "Há parametrizações obrigatórias pendentes."

    def __init__(self, details: dict[str, str]):
        self.details = details
        super().__init__()


class RegulationStorageUnavailable(ExternalServiceError):
    code = "storage_unavailable"
    default_message = "Armazenamento indisponível."
