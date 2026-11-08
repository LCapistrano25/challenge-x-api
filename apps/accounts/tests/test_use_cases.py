from unittest.mock import patch

from django.test import TestCase

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    DomainRoleMismatch,
    InvalidEmailDomain,
    NotStudentActor,
    RegistrationNumberTaken,
    RegistrationRejected,
    StudentProfileExists,
)
from apps.accounts.factories import StudentFactory, UserFactory
from apps.accounts.models import EmailDomain, Student
from apps.accounts.rules import ensure_institutional_domain
from apps.accounts.use_cases.register_student import register_student
from apps.core.models import Course


class RegisterStudentTests(TestCase):
    def setUp(self):
        EmailDomain.objects.create(name="aluno.edu.br", role=UserRole.STUDENT)
        self.course = Course.objects.get(name="Engenharia de Software")  # 8 períodos
        self.actor = UserFactory(email="ana@aluno.edu.br", role=UserRole.STUDENT)

    def register(self, **fields):
        data = {
            "actor": self.actor,
            "registration_number": "1",
            "course_id": self.course.pk,
            "term": 1,
        }
        return register_student(**{**data, **fields})

    def test_cria_perfil_de_aluno_para_o_usuario_logado(self):
        student = self.register(term=8)

        self.assertEqual(student.user, self.actor)
        self.assertEqual(student.course, self.course)
        self.assertEqual(student.term, 8)

    def test_recusa_usuario_que_nao_e_aluno(self):
        self.actor.role = UserRole.TEACHER
        self.actor.save()

        with self.assertRaises(NotStudentActor):
            self.register()
        self.assertFalse(Student.objects.exists())

    def test_recusa_email_fora_do_dominio_institucional(self):
        actor = UserFactory(email="ana@gmail.com", role=UserRole.STUDENT)

        with self.assertRaises(InvalidEmailDomain):
            self.register(actor=actor)

    def test_recusa_aluno_que_ja_tem_perfil(self):
        self.register()

        with self.assertRaises(StudentProfileExists):
            self.register(registration_number="2")

    def test_recusa_curso_inativo(self):
        self.course.active = False
        self.course.save()

        with self.assertRaisesMessage(RegistrationRejected, "Curso inválido."):
            self.register()

    def test_recusa_periodo_fora_do_curso(self):
        for term in (0, 9):
            with (
                self.subTest(term=term),
                self.assertRaisesMessage(RegistrationRejected, "entre 1 e 8"),
            ):
                self.register(term=term)
        self.assertFalse(Student.objects.exists())

    def test_recusa_matricula_em_uso(self):
        StudentFactory(registration_number="1")

        with self.assertRaises(RegistrationNumberTaken):
            self.register(registration_number="1")

    def test_cadastro_simultaneo_vira_conflito_e_nao_erro_500(self):
        StudentFactory(registration_number="1")

        # Simula a corrida: as checagens não veem o outro cadastro; o banco desempata.
        with (
            patch.object(Student.objects, "filter") as filter_,
            self.assertRaises(RegistrationNumberTaken),
        ):
            filter_.return_value.exists.return_value = False
            self.register(registration_number="1")

        self.assertFalse(Student.objects.filter(user=self.actor).exists())


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
