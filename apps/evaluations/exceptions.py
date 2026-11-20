from http import HTTPStatus

from apps.core.exceptions import BusinessRuleViolation


class TeacherNotInCourse(BusinessRuleViolation):
    code = "teacher_not_in_course"
    default_message = "O professor não tem vínculo ativo com o curso do desafio."
    http_status = HTTPStatus.FORBIDDEN
