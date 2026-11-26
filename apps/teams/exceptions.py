from http import HTTPStatus

from apps.core.exceptions import AppError


class TeamNotFound(AppError):
    code = "team_not_found"
    default_message = "Equipe não encontrada."
    http_status = HTTPStatus.NOT_FOUND
