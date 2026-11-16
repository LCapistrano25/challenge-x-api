from http import HTTPStatus

from apps.core.exceptions import BusinessRuleViolation


class InvalidEmailDomain(BusinessRuleViolation):
    code = "invalid_email_domain"
    default_message = "E-mail fora dos domínios autorizados."
    http_status = HTTPStatus.BAD_REQUEST


class DomainRoleMismatch(BusinessRuleViolation):
    code = "domain_role_mismatch"
    default_message = "Perfil não autorizado para este domínio."
    http_status = HTTPStatus.FORBIDDEN


class InvalidCredentials(BusinessRuleViolation):
    code = "invalid_credentials"
    default_message = "Credenciais inválidas."
    http_status = HTTPStatus.UNAUTHORIZED


class NotStudentActor(BusinessRuleViolation):
    code = "not_student_actor"
    default_message = "Apenas alunos podem realizar o autocadastro."
    http_status = HTTPStatus.FORBIDDEN


class RegistrationRejected(BusinessRuleViolation):
    code = "registration_rejected"
    default_message = "Não foi possível realizar o cadastro com esses dados."
    http_status = HTTPStatus.BAD_REQUEST


class StudentProfileExists(BusinessRuleViolation):
    code = "student_profile_exists"
    default_message = "Já existe um perfil de aluno associado a este usuário."
    http_status = HTTPStatus.CONFLICT


class RegistrationNumberTaken(BusinessRuleViolation):
    code = "registration_number_taken"
    default_message = "Número de matrícula já está em uso."
    http_status = HTTPStatus.CONFLICT


class ReviewerNotInCurrentEdition(BusinessRuleViolation):
    code = "reviewer_not_in_current_edition"
    default_message = "O avaliador não está vinculado à edição vigente."
    http_status = HTTPStatus.FORBIDDEN


class NotAdminActor(BusinessRuleViolation):
    code = "not_admin_actor"
    default_message = "Apenas o administrador pode realizar esta ação."
    http_status = HTTPStatus.FORBIDDEN


class EmailTaken(BusinessRuleViolation):
    code = "email_taken"
    default_message = "E-mail já cadastrado."
    http_status = HTTPStatus.CONFLICT
