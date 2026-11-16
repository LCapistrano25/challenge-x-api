import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    DomainRoleMismatch,
    EmailTaken,
    InvalidEmailDomain,
    NotAdminActor,
    NotStudentActor,
    RegistrationNumberTaken,
    RegistrationRejected,
    StudentProfileExists,
)
from apps.accounts.factories import EmailDomainFactory, StudentFactory, UserFactory
from apps.accounts.models import EmailDomain, Student
from apps.accounts.rules import ensure_institutional_domain, ensure_term_within_course
from apps.accounts.use_cases.register_external_reviewer import (
    register_external_reviewer,
)
from apps.accounts.use_cases.register_student import register_student
from apps.core.factories import CourseFactory
from apps.core.models import Course

# Autocadastro do aluno (UC21, RF19, RN10)


@pytest.fixture
def course(db):
    return Course.objects.get(name="Engenharia de Software")  # 8 períodos


@pytest.fixture
def actor(db):
    EmailDomainFactory(name="aluno.edu.br", role=UserRole.STUDENT)
    return UserFactory(email="ana@aluno.edu.br", role=UserRole.STUDENT)


@pytest.fixture
def register(actor, course):
    def call(**fields):
        data = {
            "actor": actor,
            "registration_number": "1",
            "course_id": course.pk,
            "term": 1,
        }
        return register_student(**{**data, **fields})

    return call


def test_cria_perfil_de_aluno_para_o_usuario_logado(register, actor, course):
    student = register(term=8)

    assert student.user == actor
    assert student.course == course
    assert student.term == 8


def test_recusa_usuario_que_nao_e_aluno(register, actor):
    actor.role = UserRole.TEACHER
    actor.save()

    with pytest.raises(NotStudentActor):
        register()
    assert not Student.objects.exists()


def test_recusa_email_fora_do_dominio_institucional(register):
    with pytest.raises(InvalidEmailDomain):
        register(actor=UserFactory(email="ana@gmail.com", role=UserRole.STUDENT))


def test_recusa_aluno_que_ja_tem_perfil(register):
    register()

    with pytest.raises(StudentProfileExists):
        register(registration_number="2")


def test_recusa_curso_inativo(register, course):
    course.active = False
    course.save()

    with pytest.raises(RegistrationRejected, match="Curso inválido."):
        register()


@pytest.mark.parametrize("term", [0, 9])
def test_recusa_periodo_fora_do_curso(register, term):
    with pytest.raises(ValidationError, match="entre 1 e 8"):
        register(term=term)
    assert not Student.objects.exists()


def test_recusa_matricula_em_uso(register):
    StudentFactory(registration_number="1")

    with pytest.raises(RegistrationNumberTaken):
        register(registration_number="1")


def test_cadastro_simultaneo_vira_conflito_e_nao_erro_500(register, actor, monkeypatch):
    StudentFactory(registration_number="1")

    class NothingFound:
        def exists(self):
            return False

    # Simula a corrida: as checagens não veem o outro cadastro; o banco desempata.
    monkeypatch.setattr(Student.objects, "filter", lambda **kwargs: NothingFound())
    with pytest.raises(RegistrationNumberTaken):
        register(registration_number="1")

    monkeypatch.undo()
    assert not Student.objects.filter(user=actor).exists()


# Regra do período (RN10)


@pytest.mark.parametrize(
    ("term", "valid"), [(0, False), (1, True), (8, True), (9, False)]
)
def test_periodo_vai_de_1_a_quantidade_de_periodos_do_curso(term, valid, db):
    course = CourseFactory(term_count=8)

    if valid:
        ensure_term_within_course(course, term)
    else:
        with pytest.raises(ValidationError) as error:
            ensure_term_within_course(course, term)
        assert "term" in error.value.message_dict


class EnsureInstitutionalDomainTests(TestCase):
    def test_aceita_dominio_do_perfil(self):
        EmailDomain.objects.create(
            name="professor.unicatolica.edu.br",
            active=True,
            role=UserRole.TEACHER,
        )

        ensure_institutional_domain(
            "Docente@Professor.Unicatolica.edu.br", UserRole.TEACHER
        )

    def test_rejeita_dominio_de_outro_perfil(self):
        EmailDomain.objects.create(
            name="professor.unicatolica.edu.br",
            active=True,
            role=UserRole.TEACHER,
        )

        with self.assertRaises(DomainRoleMismatch):
            ensure_institutional_domain(
                "docente@professor.unicatolica.edu.br", UserRole.STUDENT
            )

    def test_rejeita_dominio_inexistente(self):
        with self.assertRaises(InvalidEmailDomain):
            ensure_institutional_domain("usuario@gmail.com", UserRole.STUDENT)

    def test_rejeita_dominio_desativado(self):
        EmailDomain.objects.create(
            name="professor.unicatolica.edu.br",
            active=False,
            role=UserRole.TEACHER,
        )

        with self.assertRaises(InvalidEmailDomain):
            ensure_institutional_domain(
                "docente@professor.unicatolica.edu.br", UserRole.TEACHER
            )


# Cadastro do avaliador externo (UC11, RF11)


@pytest.fixture
def register_reviewer(db):
    admin = UserFactory(role=UserRole.ADMIN)

    def call(**fields):
        data = {
            "actor": admin,
            "name": "Ana Ribeiro",
            "email": "ana@empresa.com",
            "password": "SenhaForte!2026x",
            "institution": "Empresa Parceira",
        }
        return register_external_reviewer(**{**data, **fields})

    return call


def test_admin_cadastra_avaliador_com_senha_e_perfil(register_reviewer):
    reviewer = register_reviewer()

    assert reviewer.user.role == UserRole.EXTERNAL_REVIEWER
    assert reviewer.user.check_password("SenhaForte!2026x")
    assert reviewer.institution == "Empresa Parceira"


def test_avaliador_dispensa_dominio_institucional(register_reviewer):
    # Sem EmailDomain cadastrado para empresa.com, o cadastro passa (RF11).
    assert (
        register_reviewer(email="ana@qualquer.com.br").user.email
        == "ana@qualquer.com.br"
    )


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.TEACHER])
def test_so_admin_cadastra_avaliador(register_reviewer, role):
    with pytest.raises(NotAdminActor):
        register_reviewer(actor=UserFactory(role=role))


def test_email_ja_cadastrado_e_recusado(register_reviewer):
    UserFactory(email="ana@empresa.com")

    with pytest.raises(EmailTaken):
        register_reviewer()


def test_senha_fraca_aponta_o_campo(register_reviewer):
    with pytest.raises(ValidationError) as error:
        register_reviewer(password="123")

    assert "password" in error.value.message_dict
