class EditionError(Exception):
    """Base das violações de regra de negócio do app editions.

    `code` é o identificador interno de domínio; quem expõe o erro (a API, depois)
    decide como mapeá-lo.
    """

    code = "edition_error"
    default_message = "Operação não permitida para a edição."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)


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


class NotAdminActor(EditionError):
    code = "not_admin_actor"
    default_message = "Apenas o administrador pode realizar esta ação."
