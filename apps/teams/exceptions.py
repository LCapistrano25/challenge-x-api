from http import HTTPStatus

from apps.core.exceptions import AppError, BusinessRuleViolation


class TeamNotFound(AppError):
    code = "not_found"
    http_status = HTTPStatus.NOT_FOUND


class TeamCreationRejected(BusinessRuleViolation):
    """A equipe não pôde ser criada por uma regra de negócio."""


class TeamNameTaken(TeamCreationRejected):
    code = "team_name_taken"
    http_status = HTTPStatus.CONFLICT


class MemberNoteError(BusinessRuleViolation):
    """Base das violações de regra de negócio de observações."""


class MemberNoteNotFound(MemberNoteError):
    code = "not_found"
    http_status = HTTPStatus.NOT_FOUND


class MemberNotePermissionDenied(MemberNoteError):
    code = "permission_denied"
    http_status = HTTPStatus.FORBIDDEN


class TeamNotActive(BusinessRuleViolation):
    code = "team_not_active"
    default_message = "A equipe não está ativa."


class TeamNotDisqualified(BusinessRuleViolation):
    code = "team_not_disqualified"
    default_message = "A equipe não está desclassificada."


class InvalidNewLeader(BusinessRuleViolation):
    code = "invalid_new_leader"
    default_message = "O novo líder deve ser um integrante ativo, que ainda não lidera."
