from unittest.mock import patch

from django.test import TestCase

from apps.accounts.enums import UserRole
from apps.accounts.models import EmailDomain, Student, User
from apps.accounts.rules import (
    DomainRoleMismatch,
    InvalidEmailDomain,
    ensure_institutional_domain,
)
from apps.accounts.use_cases.register_student import (
    RegistrationRejected,
    register_student,
)
from apps.core.models import Course


class RegisterStudentTests(TestCase):
    def setUp(self):
        EmailDomain.objects.create(name="aluno.edu.br", role=UserRole.STUDENT)
        self.course = Course.objects.get(name="Engenharia de Software")  # 8 períodos

    def register(self, **fields):
        data = {
            "actor": None,
            "email": "ana@aluno.edu.br",
            "password": "TesteForte!2026x",
            "registration_number": "1",
            "course_id": self.course.pk,
            "term": 1,
            "confirmation_url": "http://testserver/confirm",
        }
        return register_student(**{**data, **fields})

    def test_cria_usuario_inativo_e_perfil_de_aluno(self):
        user = self.register(term=8)

        self.assertFalse(user.is_active)
        self.assertEqual(user.student.course, self.course)
        self.assertEqual(user.student.term, 8)

    def test_recusa_periodo_acima_do_curso(self):
        with self.assertRaisesMessage(RegistrationRejected, "entre 1 e 8"):
            self.register(term=9)
        self.assertFalse(User.objects.exists())

    def test_recusa_curso_inativo(self):
        self.course.active = False
        self.course.save()

        with self.assertRaisesMessage(RegistrationRejected, "Curso inválido."):
            self.register()

    def test_cadastro_simultaneo_vira_rejeicao_e_nao_erro_500(self):
        User.objects.create_user("ana@aluno.edu.br", "x")

        # Simula a corrida: a checagem de duplicidade não vê o outro cadastro.
        with (
            patch.object(User.objects, "filter") as filter_,
            self.assertRaises(RegistrationRejected),
        ):
            filter_.return_value.exists.return_value = False
            self.register(registration_number="2")

        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(Student.objects.exists())


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
