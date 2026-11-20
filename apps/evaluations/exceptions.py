from http import HTTPStatus

from apps.core.exceptions import BusinessRuleViolation


class TeacherNotInCourse(BusinessRuleViolation):
    code = "teacher_not_in_course"
    default_message = "O professor não tem vínculo ativo com o curso do desafio."
    http_status = HTTPStatus.FORBIDDEN


class FinalFormHasAnswers(BusinessRuleViolation):
    code = "final_form_has_answers"
    default_message = "O formulário já possui respostas e não pode ser alterado."


class FinalFormEmpty(BusinessRuleViolation):
    code = "final_form_empty"
    default_message = "O formulário não possui perguntas."


class FinalFormAlreadyPublished(BusinessRuleViolation):
    code = "final_form_already_published"
    default_message = "O formulário já está publicado."
