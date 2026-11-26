from http import HTTPStatus

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
