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


class NotExternalReviewerActor(BusinessRuleViolation):
    code = "not_external_reviewer_actor"
    default_message = "Apenas o avaliador externo pode realizar esta ação."
    http_status = HTTPStatus.FORBIDDEN


class FinalistNotFound(BusinessRuleViolation):
    """Projeto que não é finalista ou fica fora da abrangência do avaliador."""

    code = "not_found"
    default_message = "Projeto finalista não encontrado."
    http_status = HTTPStatus.NOT_FOUND


class FinalFormNotPublished(BusinessRuleViolation):
    code = "final_form_not_published"
    default_message = "O formulário da etapa final ainda não foi publicado."


class FinalEvaluationAlreadyFinalized(BusinessRuleViolation):
    code = "final_evaluation_already_finalized"
    default_message = "A avaliação final já foi finalizada."
