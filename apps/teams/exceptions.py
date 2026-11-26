from http import HTTPStatus

from apps.core.exceptions import BusinessRuleViolation


class MemberNoteError(BusinessRuleViolation):
    """Base das violações de regra de negócio de observações."""

    code = "member_note_error"
    default_message = "Não foi possível registrar a observação."


class MemberNoteNotFound(MemberNoteError):
    code = "not_found"
    default_message = "Recurso não encontrado."
    http_status = HTTPStatus.NOT_FOUND


class MemberNotePermissionDenied(MemberNoteError):
    code = "permission_denied"
    default_message = "Você não tem permissão para realizar esta ação."
    http_status = HTTPStatus.FORBIDDEN


class TeamNameTaken(BusinessRuleViolation):
    code = "team_name_taken"
    default_message = "Já existe equipe com este nome na edição."
