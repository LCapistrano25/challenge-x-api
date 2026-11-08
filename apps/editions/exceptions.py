from http import HTTPStatus

from apps.core.exceptions import BusinessRuleViolation


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


class InvalidTeamLimits(EditionError):
    code = "invalid_team_limits"
    default_message = (
        "Os limites devem ser maiores que zero e o mínimo não pode passar do máximo."
    )
    http_status = HTTPStatus.BAD_REQUEST


class NotAdminActor(EditionError):
    code = "not_admin_actor"
    default_message = "Apenas o administrador pode realizar esta ação."
    http_status = HTTPStatus.FORBIDDEN
