from http import HTTPStatus

from apps.core.exceptions import BusinessRuleViolation


class ProjectError(BusinessRuleViolation):
    """Base das violações de regra de negócio do app projects."""

    code = "project_error"
    default_message = "Operação não permitida para o projeto."


class NotTeamLeader(ProjectError):
    code = "not_team_leader"
    default_message = "Apenas o líder pode realizar esta ação."
    http_status = HTTPStatus.FORBIDDEN


class FormationClosed(ProjectError):
    code = "formation_closed"
    default_message = "O prazo de formação de equipes está encerrado."


class ChallengeNotEligible(ProjectError):
    code = "challenge_not_eligible"
    default_message = "O desafio não é de um curso dos integrantes ativos da equipe."
    http_status = HTTPStatus.BAD_REQUEST


class ChallengeNotSelected(ProjectError):
    code = "challenge_not_selected"
    default_message = "Escolha o desafio antes de cadastrar os dados do projeto."


class ProjectTitleTaken(ProjectError):
    code = "project_title_taken"
    default_message = "Já existe projeto com título equivalente nesta edição."
